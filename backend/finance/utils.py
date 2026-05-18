from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from .models import CONFIRMED_PAYMENT_STATUSES, Payment, StudentFee, StudentWaiver, WaiverPolicy


def _amount_due(invoice):
    raw_due = invoice.expected_amount + invoice.carried_forward + invoice.penalty_amount - invoice.waived_amount
    return max(Decimal('0.00'), raw_due)


def confirm_payment(payment):
    invoice = payment.student_fee
    if not invoice:
        return Decimal('0.00')

    money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
    total_paid = (
        Payment.objects.filter(student_fee=invoice, status__in=CONFIRMED_PAYMENT_STATUSES)
        .aggregate(total=Coalesce(Sum('amount'), money_zero))
        .get('total')
        or Decimal('0.00')
    )

    amount_due = _amount_due(invoice)
    amount_paid = min(total_paid, amount_due)

    # effective balance and credit using the canonical formulas
    invoice.paid_amount = amount_paid
    invoice.credit = max(Decimal('0.00'), total_paid - (amount_due))

    if invoice.paid_amount >= amount_due:
        invoice.status = 'paid'
    elif invoice.paid_amount > 0:
        invoice.status = 'partial'
    else:
        invoice.status = 'unpaid'

    invoice.save(update_fields=['paid_amount', 'credit', 'status', 'updated_at'])
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
        policy = waiver.policy
        if policy.discount_type == 'percentage':
            waived = invoice.expected_amount * (policy.discount_value / Decimal('100'))
        else:
            waived = min(policy.discount_value, invoice.expected_amount)

        waived = waived.quantize(Decimal('0.01'))
        invoice.waived_amount = waived
        invoice.waiver = waiver
        invoice.waiver_reason = policy.get_category_display()

        # Recalculate status
        net_due = invoice.expected_amount - waived + invoice.carried_forward + invoice.penalty_amount
        net_due = max(Decimal('0.00'), net_due)

        total_paid = (
            Payment.objects.filter(student_fee=invoice, status__in=CONFIRMED_PAYMENT_STATUSES)
            .aggregate(total=Coalesce(Sum('amount'), Value(Decimal('0.00'))))
            .get('total')
            or Decimal('0.00')
        )

        if total_paid >= net_due:
            invoice.status = 'paid'
            invoice.credit = max(
                Decimal('0.00'),
                total_paid - net_due
            )
            invoice.paid_amount = min(total_paid, net_due)
        elif total_paid > 0:
            invoice.status = 'partial'
            invoice.credit = Decimal('0.00')
            invoice.paid_amount = min(total_paid, net_due)
        else:
            invoice.status = 'unpaid'
            invoice.credit = Decimal('0.00')
            invoice.paid_amount = Decimal('0.00')

        invoice.save()


def remove_waiver_from_invoices(waiver):
    from decimal import Decimal
    invoices = StudentFee.objects.filter(waiver=waiver)

    for invoice in invoices:
        invoice.waived_amount = Decimal('0.00')
        invoice.waiver = None
        invoice.waiver_reason = ''
        invoice.credit = Decimal('0.00')

        # Recalculate status without waiver
        total_paid = (
            Payment.objects.filter(student_fee=invoice, status__in=CONFIRMED_PAYMENT_STATUSES)
            .aggregate(total=Coalesce(Sum('amount'), Value(Decimal('0.00'))))
            .get('total')
            or Decimal('0.00')
        )

        amount_due = max(
            Decimal('0.00'),
            invoice.expected_amount + invoice.carried_forward + invoice.penalty_amount
        )

        if total_paid >= amount_due:
            invoice.status = 'paid'
            invoice.credit = max(Decimal('0.00'), total_paid - amount_due)
            invoice.paid_amount = min(total_paid, amount_due)
        elif total_paid > 0:
            invoice.status = 'partial'
            invoice.paid_amount = min(total_paid, amount_due)
        else:
            invoice.status = 'unpaid'
            invoice.paid_amount = Decimal('0.00')

        invoice.save()


def get_carry_forward(student, current_term, current_year):
    from decimal import Decimal

    previous = StudentFee.objects.filter(
        student=student
    ).exclude(
        fee_structure__term=current_term,
        fee_structure__academic_year=current_year
    ).select_related('fee_structure').order_by('-fee_structure__academic_year', '-fee_structure__term').first()

    if not previous:
        return Decimal('0.00')

    # Net due = what they actually owed after waiver
    net_due = max(
        Decimal('0.00'),
        previous.expected_amount + previous.carried_forward + previous.penalty_amount - previous.waived_amount
    )
    
    # Carry forward = net_due minus what they paid
    # Positive = arrears (add to next invoice)
    # Negative = credit (deduct from next invoice)
    carry_forward = net_due - previous.paid_amount
    
    return carry_forward


def calculate_waived_amount(student, base_amount, term, year):
    """Calculate waived amount based on student's active waiver policy."""
    waiver = StudentWaiver.objects.filter(
        student=student,
        is_active=True,
        valid_from_year__lte=year,
    ).filter(
        Q(valid_until_year__isnull=True) | Q(valid_until_year__gte=year)
    ).select_related('policy').first()

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

