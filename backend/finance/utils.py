from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from .models import CONFIRMED_PAYMENT_STATUSES, Payment, StudentFee, StudentWaiver, WaiverPolicy


TERM_ORDER = {
    'term1': 1,
    'term2': 2,
    'term3': 3,
    'annual': 4,
}


def _previous_term_and_year(current_term, current_year):
    if current_term == 'term1':
        return 'term3', current_year - 1
    if current_term == 'term2':
        return 'term1', current_year
    if current_term == 'term3':
        return 'term2', current_year
    if current_term == 'annual':
        return 'annual', current_year - 1
    return None, None


def _term_within_bounds(current_term, current_year, waiver):
    if current_term not in TERM_ORDER:
        return False
    if waiver.valid_from_year is None:
        return False

    if current_term == 'annual':
        if waiver.valid_from_term != 'annual':
            return False
        if waiver.valid_until_year is None:
            return current_year >= waiver.valid_from_year
        if waiver.valid_until_term and waiver.valid_until_term != 'annual':
            return False
        return waiver.valid_from_year <= current_year <= waiver.valid_until_year

    if waiver.valid_from_term == 'annual':
        return False
    if waiver.valid_until_term == 'annual':
        return False

    start_key = (waiver.valid_from_year, TERM_ORDER.get(waiver.valid_from_term))
    current_key = (current_year, TERM_ORDER.get(current_term))

    if waiver.valid_until_year is None:
        return current_key >= start_key

    end_term = waiver.valid_until_term or waiver.valid_from_term
    end_key = (waiver.valid_until_year, TERM_ORDER.get(end_term))
    return start_key <= current_key <= end_key


def _invoice_base_due(invoice):
    """
    The base obligation for a single term's invoice:
      expected_amount + carried_forward (snapshot from generation) + penalty - waived

    carried_forward here is the ORIGINAL arrears baked in at invoice-generation time.
    It is a snapshot and must NOT be re-written by recalculate_student_fees().
    """
    return max(
        Decimal('0.00'),
        invoice.expected_amount
        + invoice.carried_forward
        + invoice.penalty_amount
        - invoice.waived_amount,
    )


def confirm_payment(payment):
    """Confirm a single payment and cascade recalculation to all invoices."""
    invoice = payment.student_fee
    if not invoice:
        return Decimal('0.00')

    recalculate_student_fees(invoice.student)

    invoice.refresh_from_db()
    return invoice.credit


def apply_waiver_to_invoices(waiver):
    from decimal import Decimal
    from .models import FeeStructure, StudentFee

    invoices = StudentFee.objects.filter(
        student=waiver.student,
        fee_structure__academic_year__gte=waiver.valid_from_year,
    ).select_related('fee_structure')

    if waiver.valid_until_year:
        invoices = invoices.filter(
            fee_structure__academic_year__lte=waiver.valid_until_year
        )

    for invoice in invoices:
        if not _term_within_bounds(invoice.fee_structure.term, invoice.fee_structure.academic_year, waiver):
            continue
        policy = waiver.policy
        if policy.discount_type == 'percentage':
            waived = invoice.expected_amount * (policy.discount_value / Decimal('100'))
        else:
            waived = min(policy.discount_value, invoice.expected_amount)

        waived = waived.quantize(Decimal('0.01'))
        invoice.waived_amount = waived
        invoice.waiver = waiver
        invoice.waiver_reason = policy.get_category_display()
        invoice.save(update_fields=['waived_amount', 'waiver', 'waiver_reason'])

    # Cascade recalculation after waiver change
    recalculate_student_fees(waiver.student)


def remove_waiver_from_invoices(waiver):
    invoices = StudentFee.objects.filter(waiver=waiver)
    for invoice in invoices:
        invoice.waived_amount = Decimal('0.00')
        invoice.waiver = None
        invoice.waiver_reason = ''
        invoice.save(update_fields=['waived_amount', 'waiver', 'waiver_reason'])

    recalculate_student_fees(waiver.student)


def _invoice_net_balance(invoice):
    """
    True net balance for carry-forward purposes:
      positive = arrears still owed
      negative = credit to carry forward

    Uses the stored carried_forward snapshot (not re-derived) so the
    carry-forward chain doesn't compound across generations.
    """
    total_due = _invoice_base_due(invoice)
    total_paid = (
        Payment.objects.filter(student_fee=invoice, status__in=CONFIRMED_PAYMENT_STATUSES)
        .aggregate(total=Coalesce(Sum('amount'), Value(Decimal('0.00'))))
        .get('total')
        or Decimal('0.00')
    )
    return total_due - total_paid  # positive = still owed, negative = credit


def get_carry_forward(student, current_term, current_year):
    """
    Net balance from the immediately previous term.
    Positive = arrears; negative = credit.
    Called ONLY at invoice-generation time to snapshot the CF for a new invoice.
    """
    previous_term, previous_year = _previous_term_and_year(current_term, current_year)
    if not previous_term or previous_year is None:
        return Decimal('0.00')

    previous = StudentFee.objects.filter(
        student=student,
        tenant=getattr(student, 'tenant', None),
        fee_structure__term=previous_term,
        fee_structure__academic_year=previous_year,
    ).select_related('fee_structure').first()

    if not previous:
        return Decimal('0.00')

    return _invoice_net_balance(previous)


def recalculate_student_fees(student):
    """
    Recalculate paid_amount, credit, and status for ALL of a student's invoices
    in chronological order, flowing surplus credit forward.

    KEY INVARIANT: carried_forward is a snapshot set at invoice-generation time
    and is NEVER modified here.

    Credit field semantics:
      credit is ONLY set on the LAST invoice in the chain if there is remaining
      surplus after all invoices are processed. Intermediate invoices always have
      credit=0 — the surplus is cascaded via cumulative_credit into the next
      invoice's paid_amount. This prevents double-counting where the same $500
      surplus would appear as credit on invoice N AND paid_amount on invoice N+1.
    """
    invoices = (
        StudentFee.objects.filter(student=student, tenant=student.tenant)
        .select_related('fee_structure')
        .order_by('fee_structure__academic_year', 'fee_structure__term')
    )

    term_order = {'term1': 1, 'term2': 2, 'term3': 3, 'annual': 4}
    invoices = sorted(
        invoices,
        key=lambda inv: (
            inv.fee_structure.academic_year,
            term_order.get(inv.fee_structure.term, 99),
        ),
    )

    cumulative_credit = Decimal('0.00')

    for invoice in invoices:
        # Base obligation for this term (uses snapshot carried_forward — not re-derived)
        base_due = _invoice_base_due(invoice)

        # Payments actually recorded against this specific invoice
        term_payments = (
            Payment.objects.filter(student_fee=invoice, status__in=CONFIRMED_PAYMENT_STATUSES)
            .aggregate(total=Coalesce(Sum('amount'), Value(Decimal('0.00'))))
            .get('total')
            or Decimal('0.00')
        )

        # Total available = own payments + credit cascaded from earlier terms
        available = term_payments + cumulative_credit

        if base_due == Decimal('0.00'):
            # Fully waived or zero-fee term: pass all credit through unchanged
            invoice.paid_amount = Decimal('0.00')
            invoice.credit = Decimal('0.00')
            invoice.status = 'paid'
            cumulative_credit = available
        elif available >= base_due:
            invoice.paid_amount = base_due
            # credit is cleared here — surplus is tracked in cumulative_credit
            # and will be written to the final invoice after the loop
            invoice.credit = Decimal('0.00')
            invoice.status = 'paid'
            cumulative_credit = available - base_due
        elif available > Decimal('0.00'):
            invoice.paid_amount = available
            invoice.credit = Decimal('0.00')
            invoice.status = 'partial'
            cumulative_credit = Decimal('0.00')
        else:
            invoice.paid_amount = Decimal('0.00')
            invoice.credit = Decimal('0.00')
            invoice.status = 'unpaid'
            cumulative_credit = Decimal('0.00')

        invoice.save(update_fields=['paid_amount', 'credit', 'status', 'updated_at'])

    # Write any remaining surplus onto the last invoice so it is visible
    # to the student and to confirm_payment callers. This is the single
    # canonical location of the credit balance.
    if invoices and cumulative_credit > Decimal('0.00'):
        last = invoices[-1]
        last.credit = cumulative_credit
        last.save(update_fields=['credit', 'updated_at'])


def calculate_waived_amount(student, base_amount, term, year):
    """Calculate waived amount based on student's active waiver policy."""
    waivers = (
        StudentWaiver.objects.filter(
            student=student,
            is_active=True,
            valid_from_year__lte=year,
        )
        .filter(Q(valid_until_year__isnull=True) | Q(valid_until_year__gte=year))
        .select_related('policy')
        .order_by('-valid_from_year', '-valid_from_term')
    )

    waiver = next((item for item in waivers if _term_within_bounds(term, year, item)), None)

    if not waiver:
        return Decimal('0.00'), None

    policy = waiver.policy
    if policy.discount_type == 'percentage':
        waived = base_amount * (policy.discount_value / Decimal('100'))
    else:
        waived = min(policy.discount_value, base_amount)

    return waived.quantize(Decimal('0.01')), waiver


def get_sibling_discount(student):
    """Check if student qualifies for sibling discount."""
    if not student.primary_guardian:
        return None

    siblings = (
        student.__class__.objects.filter(
            primary_guardian=student.primary_guardian,
            is_active=True,
        )
        .exclude(id=student.id)
        .count()
    )
    if siblings == 0:
        return None

    return WaiverPolicy.objects.filter(
        category='sibling', is_active=True, tenant=student.tenant
    ).first()