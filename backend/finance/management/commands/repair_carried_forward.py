"""
Management command: repair_carried_forward

Run this ONCE after deploying the fixed utils.py to heal carried_forward
values that were corrupted by the old recalculate_student_fees() logic.

The old code kept rewriting carried_forward as the unpaid balance of the
current term, causing it to compound across terms. The correct value is:
  - 0 for the FIRST invoice a student has (nothing previous to carry from)
  - For every subsequent invoice: the NET balance of the immediately
    preceding term's invoice AT THE TIME IT WAS GENERATED.

Since we cannot know what the balance was at generation time for old rows,
we derive it from first principles:
  previous_net = previous_base_due - previous_confirmed_payments

where previous_base_due = previous.expected_amount + previous.carried_forward
(using the ALREADY-REPAIRED previous row, traversed in chronological order).

This is idempotent — safe to run multiple times.

Usage:
    python manage.py repair_carried_forward
    python manage.py repair_carried_forward --dry-run
    python manage.py repair_carried_forward --tenant-slug=demo-school
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce

from finance.models import CONFIRMED_PAYMENT_STATUSES, Payment, StudentFee
from students.models import Student


TERM_ORDER = {'term1': 1, 'term2': 2, 'term3': 3, 'annual': 4}


def _confirmed_payments_for(invoice):
    return (
        Payment.objects.filter(
            student_fee=invoice,
            status__in=CONFIRMED_PAYMENT_STATUSES,
        )
        .aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))
        ['total']
        or Decimal('0.00')
    )


def _sort_key(inv):
    return (
        inv.fee_structure.academic_year,
        TERM_ORDER.get(inv.fee_structure.term, 99),
    )


def repair_student(student, dry_run=False, verbosity=1):
    """
    Repair carried_forward for one student's invoices in chronological order.
    Returns a list of (invoice_id, old_cf, new_cf) tuples for changed rows.
    """
    invoices = list(
        StudentFee.objects
        .filter(student=student, tenant=student.tenant)
        .select_related('fee_structure')
        .order_by('fee_structure__academic_year', 'fee_structure__term')
    )
    invoices.sort(key=_sort_key)

    changes = []
    prev_net_balance = Decimal('0.00')  # net owed after first invoice

    for i, invoice in enumerate(invoices):
        correct_cf = prev_net_balance if i > 0 else Decimal('0.00')
        # Clamp: CF cannot make expected_amount go negative
        correct_cf = max(correct_cf, -invoice.expected_amount)

        old_cf = invoice.carried_forward

        if old_cf != correct_cf:
            changes.append((str(invoice.id), old_cf, correct_cf, invoice.fee_structure.term, invoice.fee_structure.academic_year))
            if not dry_run:
                invoice.carried_forward = correct_cf
                invoice.save(update_fields=['carried_forward'])

        # Compute the net balance for THIS invoice using the (now corrected) CF
        # base_due uses the corrected CF value
        corrected_base_due = max(
            Decimal('0.00'),
            invoice.expected_amount + correct_cf + invoice.penalty_amount - invoice.waived_amount,
        )
        paid = _confirmed_payments_for(invoice)
        # Net balance = what's still owed (positive) or credit (negative)
        prev_net_balance = corrected_base_due - paid

    return changes


class Command(BaseCommand):
    help = 'Repair corrupted carried_forward values caused by old recalculate_student_fees() logic.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without writing to the DB.',
        )
        parser.add_argument(
            '--tenant-slug',
            type=str,
            default=None,
            help='Restrict repair to a single tenant by slug.',
        )
        parser.add_argument(
            '--student-id',
            type=int,
            default=None,
            help='Repair a single student by ID (for testing).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tenant_slug = options['tenant_slug']
        student_id = options['student_id']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be written.\n'))

        qs = Student.objects.select_related('tenant').filter(is_active=True)

        if tenant_slug:
            qs = qs.filter(tenant__slug=tenant_slug)
            self.stdout.write(f'Filtering to tenant slug: {tenant_slug}\n')

        if student_id:
            qs = qs.filter(id=student_id)
            self.stdout.write(f'Filtering to student id: {student_id}\n')

        total_students = 0
        total_changed_rows = 0
        total_changed_students = 0

        with transaction.atomic():
            for student in qs.iterator():
                total_students += 1
                changes = repair_student(student, dry_run=dry_run, verbosity=options['verbosity'])

                if changes:
                    total_changed_students += 1
                    total_changed_rows += len(changes)
                    if options['verbosity'] >= 1:
                        self.stdout.write(
                            f'  Student {student.admission_number} ({student.get_full_name()}): '
                            f'{len(changes)} invoice(s) changed'
                        )
                    for inv_id, old_cf, new_cf, term, year in changes:
                        if options['verbosity'] >= 2:
                            self.stdout.write(
                                f'    [{term} {year}] carried_forward: {old_cf} -> {new_cf}'
                            )

            if dry_run:
                # Roll back everything — we're just reporting
                transaction.set_rollback(True)

        self.stdout.write('\n')
        self.stdout.write(self.style.SUCCESS(
            f'Done. Scanned {total_students} students. '
            f'{"Would update" if dry_run else "Updated"} {total_changed_rows} invoice rows '
            f'across {total_changed_students} students.'
        ))

        if not dry_run and total_changed_rows > 0:
            self.stdout.write(
                '\nNow run the following to recalculate paid_amount/credit/status '
                'using the corrected carried_forward values:\n'
                '  python manage.py shell -c "'
                'from students.models import Student; '
                'from finance.utils import recalculate_student_fees; '
                '[recalculate_student_fees(s) for s in Student.objects.select_related(\'tenant\').filter(is_active=True)]'
                '"'
            )
