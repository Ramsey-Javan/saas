"""
Management command: diagnose_billing_gap

Read-only diagnostic to find exactly which student/invoice is causing a
mismatch between expected dashboard totals and actual generated invoices.

Does NOT modify any data. Safe to run anytime.

Usage:
    python manage.py diagnose_billing_gap --classroom-id=<id>
    python manage.py diagnose_billing_gap --tenant-slug=demo-school
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum, Count, Value, DecimalField
from django.db.models.functions import Coalesce

from finance.models import FeeStructure, StudentFee
from students.models import Student, Classroom


class Command(BaseCommand):
    help = 'Read-only diagnostic to find the source of a billing total discrepancy.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant-slug', type=str, default=None)
        parser.add_argument('--classroom-id', type=int, default=None)

    def handle(self, *args, **options):
        tenant_slug = options['tenant_slug']
        classroom_id = options['classroom_id']

        fs_qs = FeeStructure.objects.select_related('classroom', 'tenant')
        if tenant_slug:
            fs_qs = fs_qs.filter(tenant__slug=tenant_slug)
        if classroom_id:
            fs_qs = fs_qs.filter(classroom_id=classroom_id)

        self.stdout.write(self.style.WARNING('\n=== 1. Fee structures (should be exactly one per classroom+term+year) ===\n'))
        dupe_check = {}
        for fs in fs_qs.order_by('classroom__name', 'academic_year', 'term'):
            key = (fs.tenant_id, fs.classroom_id, fs.term, fs.academic_year)
            dupe_check.setdefault(key, []).append(fs)
            self.stdout.write(
                f'  [{fs.id}] {fs.classroom.name} | {fs.term} {fs.academic_year} | '
                f'base={fs.base_amount} | active={fs.is_active}'
            )

        dupes = {k: v for k, v in dupe_check.items() if len(v) > 1}
        if dupes:
            self.stdout.write(self.style.ERROR(f'\n  !! Found {len(dupes)} duplicate FeeStructure groups (should be impossible — check unique_together):'))
            for key, items in dupes.items():
                self.stdout.write(f'     {key}: {[i.id for i in items]}')
        else:
            self.stdout.write(self.style.SUCCESS('  No duplicate fee structures found. (Good — unique_together is holding.)'))

        self.stdout.write(self.style.WARNING('\n=== 2. Per-student invoice count & total (flagging anomalies) ===\n'))

        sf_qs = StudentFee.objects.select_related('student', 'fee_structure', 'student__classroom')
        if tenant_slug:
            sf_qs = sf_qs.filter(tenant__slug=tenant_slug)
        if classroom_id:
            sf_qs = sf_qs.filter(student__classroom_id=classroom_id)

        per_student = {}
        for sf in sf_qs:
            key = sf.student_id
            per_student.setdefault(key, {'student': sf.student, 'invoices': []})
            per_student[key]['invoices'].append(sf)

        # Determine the "expected" invoice count per classroom = number of
        # active fee structures that exist for that classroom.
        fs_count_by_classroom = {}
        for fs in fs_qs.filter(is_active=True):
            fs_count_by_classroom.setdefault(fs.classroom_id, 0)
            fs_count_by_classroom[fs.classroom_id] += 1

        flagged = []
        total_gross = Decimal('0.00')

        for student_id, data in per_student.items():
            student = data['student']
            invoices = data['invoices']
            classroom_id_for_student = student.classroom_id
            expected_count = fs_count_by_classroom.get(classroom_id_for_student, None)

            gross = sum(
                (inv.expected_amount + inv.penalty_amount - inv.waived_amount)
                for inv in invoices
            )
            total_gross += gross

            is_active_student = getattr(student, 'is_active', True)
            student_status = getattr(student, 'status', None)

            anomaly_reasons = []
            if expected_count is not None and len(invoices) != expected_count:
                anomaly_reasons.append(
                    f'has {len(invoices)} invoice(s), expected {expected_count} for this classroom'
                )
            if not is_active_student or (student_status and str(student_status).lower() not in ('active',)):
                anomaly_reasons.append(f'student is_active={is_active_student} status={student_status}')

            if anomaly_reasons:
                flagged.append((student, invoices, gross, anomaly_reasons))

        if flagged:
            self.stdout.write(self.style.ERROR(f'  !! {len(flagged)} student(s) with anomalies:\n'))
            for student, invoices, gross, reasons in flagged:
                self.stdout.write(
                    f'    {student.admission_number} ({student.get_full_name()}) '
                    f'classroom={student.classroom} gross_due={gross}'
                )
                for r in reasons:
                    self.stdout.write(f'      -> {r}')
                for inv in invoices:
                    self.stdout.write(
                        f'         invoice [{inv.id}] {inv.fee_structure.term} {inv.fee_structure.academic_year} '
                        f'expected={inv.expected_amount} penalty={inv.penalty_amount} waived={inv.waived_amount} '
                        f'status={inv.status}'
                    )
        else:
            self.stdout.write(self.style.SUCCESS('  No per-student anomalies found by count/active-status check.'))

        self.stdout.write(self.style.WARNING(f'\n=== 3. Totals ===\n'))
        self.stdout.write(f'  Total students with invoices: {len(per_student)}')
        self.stdout.write(f'  Sum of gross_due (expected+penalty-waived) across ALL invoices: KES {total_gross:,.2f}')

        active_students_count = Student.objects.filter(
            classroom_id=classroom_id, is_active=True
        ).count() if classroom_id else None
        if active_students_count is not None:
            self.stdout.write(f'  Active students currently in this classroom: {active_students_count}')

        self.stdout.write(self.style.WARNING('\n=== 4. Per-classroom breakdown (find which classroom holds the gap) ===\n'))
        by_classroom = {}
        for student_id, data in per_student.items():
            student = data['student']
            invoices = data['invoices']
            classroom = student.classroom
            key = (classroom.id if classroom else None, str(classroom) if classroom else 'NO CLASSROOM')
            entry = by_classroom.setdefault(key, {'students': 0, 'invoices': 0, 'gross': Decimal('0.00')})
            entry['students'] += 1
            entry['invoices'] += len(invoices)
            entry['gross'] += sum(
                (inv.expected_amount + inv.penalty_amount - inv.waived_amount)
                for inv in invoices
            )

        for (cid, cname), entry in sorted(by_classroom.items(), key=lambda x: -x[1]['gross']):
            self.stdout.write(
                f'  classroom_id={cid} | {cname} | students={entry["students"]} | '
                f'invoices={entry["invoices"]} | gross_due=KES {entry["gross"]:,.2f}'
            )

        self.stdout.write(self.style.WARNING('\nDone. No data was modified.\n'))