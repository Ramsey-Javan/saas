"""Fee structure and student fee (invoice) viewsets."""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import DecimalField, ExpressionWrapper,F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_date
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from students.models import Classroom, Student

from ..models import FeeStructure, StudentFee, Payment, CONFIRMED_PAYMENT_STATUSES
from ..permissions import IsAdminOrBursar
from ..serializers import FeeStructureSerializer, StudentFeeSerializer, PaymentSerializer
from ..utils import (
    calculate_waived_amount,
    get_carry_forward,
    get_sibling_discount,
)
from .mixins import (
    TenantScopedMixin,
    _confirmed_payment_filter,
    _recalculate_invoice, 
    gross_due_expression,
    outstanding_expression,
    total_due_expression,
)


class FeeStructureViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = FeeStructure.objects.select_related('tenant', 'classroom').all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAdminOrBursar]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['classroom', 'term', 'academic_year', 'is_active']
    search_fields = ['classroom__name', 'academic_year']

    def perform_create(self, serializer):
        try:
            super().perform_create(serializer)
        except IntegrityError:
            raise ValidationError(
                {'detail': 'Fee structure already exists for this class, term, and academic year.'}
            )


class StudentFeeViewSet(TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StudentFee.objects.select_related(
        'tenant',
        'student',
        'student__classroom',
        'fee_structure',
    ).all()
    serializer_class = StudentFeeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'student__classroom', 'fee_structure__term', 'fee_structure__academic_year']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']

    def get_queryset(self):
        qs = super().get_queryset()
        money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
        qs = qs.annotate(
            paid_total=Coalesce(
                Sum('payments__amount', filter=_confirmed_payment_filter()),
                money_zero,
            )
        )
        status_in = self.request.query_params.get('status__in')
        student_id = self.request.query_params.get('student')
        term = self.request.query_params.get('term')
        if status_in:
            qs = qs.filter(status__in=[item.strip() for item in status_in.split(',') if item.strip()])
        if student_id:
            qs = qs.filter(student_id=student_id)
        if term:
            qs = qs.filter(fee_structure__term=term)
        return qs.order_by(
            '-fee_structure__academic_year',
            'fee_structure__term',
            'student__admission_number',
        )

    @action(detail=False, methods=['post'], permission_classes=[IsAdminOrBursar])
    def generate_bulk(self, request):
        from decimal import Decimal
        from django.utils.dateparse import parse_date
        from django.db import transaction
        from students.models import Student, Classroom
        from finance.models import FeeStructure, StudentFee
        from finance.utils import get_carry_forward, calculate_waived_amount, get_sibling_discount, recalculate_student_fees

        classroom_id = request.data.get('classroom')
        term = request.data.get('term')
        academic_year = request.data.get('academic_year')
        due_date = parse_date(str(request.data.get('due_date', '')))

        if not all([classroom_id, term, academic_year]):
            return Response(
                {'error': 'Missing required fields: classroom, term, academic_year.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            academic_year = int(academic_year)
        except (TypeError, ValueError):
            return Response({'error': 'Academic year must be a valid integer start year.'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = getattr(request.user, 'tenant', None)
        try:
            classroom = Classroom.objects.get(id=classroom_id, tenant=tenant)
            structure = FeeStructure.objects.get(
                classroom=classroom,
                term=term,
                academic_year=academic_year,
                tenant=tenant,
                is_active=True,
            )
        except Classroom.DoesNotExist:
            return Response({'error': 'Classroom not found.'}, status=status.HTTP_404_NOT_FOUND)
        except FeeStructure.DoesNotExist:
            return Response({'error': 'Active fee structure not found.'}, status=status.HTTP_404_NOT_FOUND)

        invoice_due_date = due_date or structure.due_date
        if not invoice_due_date:
            return Response(
                {'error': 'Missing due date. Set due_date on the fee structure or supply it in the request.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        students = Student.objects.filter(
            classroom=classroom,
            tenant=tenant,
            status=Student.Status.ACTIVE,
            is_active=True,
        )
        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for student in students:
                previous_fees = StudentFee.objects.select_related('fee_structure').filter(
                    tenant=tenant,
                    student=student,
                ).exclude(
                    fee_structure__term=term,
                    fee_structure__academic_year=academic_year,
                )
                for previous_fee in previous_fees:
                    _recalculate_invoice(previous_fee)

                recalculate_student_fees(student)

                carried_forward = get_carry_forward(student, term, academic_year)

                if structure.base_amount + carried_forward < Decimal('0.00'):
                    carried_forward = -structure.base_amount

                waived_amount, waiver = calculate_waived_amount(student, structure.base_amount, term, academic_year)

                if waived_amount == 0:
                    sibling_policy = get_sibling_discount(student)
                    if sibling_policy:
                        if sibling_policy.discount_type == 'percentage':
                            waived_amount = structure.base_amount * (sibling_policy.discount_value / Decimal('100'))
                        else:
                            waived_amount = min(sibling_policy.discount_value, structure.base_amount)
                        waived_amount = waived_amount.quantize(Decimal('0.01'))

                _, created = StudentFee.objects.get_or_create(
                    tenant=tenant,
                    student=student,
                    fee_structure=structure,
                    defaults={
                        'expected_amount': structure.base_amount,
                        'waived_amount': waived_amount,
                        'waiver': waiver,
                        'carried_forward': carried_forward,
                        'due_date': invoice_due_date,
                        'status': 'unpaid',
                    },
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

            for student in students:
                recalculate_student_fees(student)

        if created_count == 0 and skipped_count > 0:
            message = (
                f'No new invoices needed — all {skipped_count} student(s) in this class '
                f'already have an invoice for this term.'
            )
        elif created_count > 0 and skipped_count > 0:
            message = (
                f'Backfilled {created_count} new invoice(s) (e.g. for recently admitted students). '
                f'{skipped_count} student(s) already had one.'
            )
        else:
            message = f'Generated {created_count} invoice(s).'

        # Log bulk invoice generation
        from activity.utils import log_activity
        from activity.models import ActivityLog

        log_activity(
            tenant=tenant,
            activity_type=ActivityLog.ActivityType.INVOICE_BULK_GENERATED,
            title="Bulk invoices generated",
            description=message,
            actor=request.user,
            metadata={
                'created_count': created_count,
                'skipped_count': skipped_count,
                'classroom': classroom.name,
                'term': term,
                'academic_year': academic_year,
            },
        )

        return Response(
            {
                'message': message,
                'created_count': created_count,
                'skipped_count': skipped_count,
            },
            status=status.HTTP_201_CREATED,
        )
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrBursar])
    def defaulters(self, request):
        # Per-row check: each invoice's OWN outstanding balance (including its
        # own legitimate carried_forward). This lists individual overdue
        # invoices -- it does NOT sum across multiple invoices, so using the
        # CF-inclusive outstanding_expression() here is correct and safe.
        qs = (
            self.get_queryset()
            .annotate(outstanding=outstanding_expression())
            .filter(
                outstanding__gt=0,
                due_date__lt=timezone.localdate(),
                status__in=['unpaid', 'partial', 'overdue'],
            )
        )
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrBursar])
    def class_report(self, request):
        classroom_id = request.query_params.get('classroom')
        qs = self.get_queryset()
        if classroom_id:
            qs = qs.filter(student__classroom_id=classroom_id)

        money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))

        # CRITICAL: expected_total and collected_total are computed via TWO
        # SEPARATE queries, never combined in one .annotate()/.aggregate() call.
        #
        # Sum(gross_due_expression()) is a pure StudentFee-table value (no join
        # needed). Sum('payments__amount', ...) requires a JOIN to Payment.
        # Combining both Sums in the SAME query makes Django join Payment once
        # for the whole query -- and ANY invoice with more than one matching
        # confirmed payment row gets its (unrelated) gross_due counted once per
        # matching payment row, silently inflating expected_total. This is the
        # documented Django "combining multiple aggregations" pitfall:
        # https://docs.djangoproject.com/en/stable/topics/db/aggregation/#combining-multiple-aggregations
        #
        # Fix: compute expected_total per classroom with NO Payment join at all,
        # and collected_total with a separate Payment-only query, then merge
        # the two dicts in Python.
        expected_by_classroom = {
            row['student__classroom__id']: row
            for row in (
                qs.values('student__classroom__id', 'student__classroom__name')
                .annotate(expected_total=Coalesce(Sum(gross_due_expression()), money_zero))
            )
        }

        collected_rows = (
            Payment.objects.filter(
                student_fee__in=qs,
                status__in=CONFIRMED_PAYMENT_STATUSES,
            )
            .values('student_fee__student__classroom_id')
            .annotate(collected_total=Coalesce(Sum('amount'), money_zero))
        )
        collected_by_classroom = {
            row['student_fee__student__classroom_id']: row['collected_total']
            for row in collected_rows
        }

        report = []
        for cid, row in expected_by_classroom.items():
            expected = row['expected_total']
            collected = collected_by_classroom.get(cid, Decimal('0.00'))
            report.append({
                'student__classroom__id': cid,
                'student__classroom__name': row['student__classroom__name'],
                'expected_total': expected,
                'collected_total': collected,
                'outstanding': expected - collected,
            })
        report.sort(key=lambda r: r['student__classroom__name'] or '')
        return Response(report)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrBursar])
    def term_summary(self, request):
        qs = self.get_queryset()
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')
        if term:
            qs = qs.filter(fee_structure__term=term)
        if academic_year:
            try:
                academic_year = int(academic_year)
            except (TypeError, ValueError):
                return Response({'error': 'Academic year must be a valid integer start year.'}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(fee_structure__academic_year=academic_year)

        money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
        # expected_total/total_waived are both pure StudentFee-table aggregates
        # (no join needed) -- safe to combine in one aggregate() call.
        summary = qs.aggregate(
            expected_total=Coalesce(Sum(gross_due_expression()), money_zero),
            total_waived=Coalesce(Sum('waived_amount'), money_zero),
        )
        # collected_total via a SEPARATE query against Payment directly.
        # See class_report() for why this must never be combined with
        # expected_total in the same aggregate()/annotate() call (Sum-with-join
        # fan-out -- any invoice with multiple matching payments would inflate
        # expected_total too).
        summary['collected_total'] = Payment.objects.filter(
            student_fee__in=qs,
            status__in=CONFIRMED_PAYMENT_STATUSES,
        ).aggregate(total=Coalesce(Sum('amount'), money_zero))['total']
        summary['outstanding_total'] = summary['expected_total'] - summary['collected_total']
        return Response(summary)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrBursar])
    def dashboard_summary(self, request):
        qs = self.get_queryset()
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')
        if term:
            qs = qs.filter(fee_structure__term=term)
        if academic_year:
            try:
                academic_year = int(academic_year)
            except (TypeError, ValueError):
                return Response({'error': 'Academic year must be a valid integer start year.'}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(fee_structure__academic_year=academic_year)

        money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))

        # expected_total/total_waived are both pure StudentFee-table aggregates
        # (no join needed) -- safe to combine in one aggregate() call.
        summary = qs.aggregate(
            expected_total=Coalesce(Sum(gross_due_expression()), money_zero),
            total_waived=Coalesce(Sum('waived_amount'), money_zero),
        )
        # collected_total via a SEPARATE query against Payment directly.
        # CRITICAL: never combine this with expected_total in one aggregate()/
        # annotate() call -- Sum(gross_due_expression()) needs no join, but
        # Sum('payments__amount', ...) requires joining Payment; combining both
        # in a single query makes Django join Payment for the WHOLE query, and
        # any invoice with more than one matching confirmed payment gets its
        # (unrelated) gross_due counted once per matching payment row. This is
        # exactly what inflated "Total Expected" on the Bursar Dashboard.
        summary['collected_total'] = Payment.objects.filter(
            student_fee__in=qs,
            status__in=CONFIRMED_PAYMENT_STATUSES,
        ).aggregate(total=Coalesce(Sum('amount'), money_zero))['total']
        summary['outstanding_total'] = summary['expected_total'] - summary['collected_total']

        paid_qs = qs.annotate(
            paid_total=Coalesce(
                Sum('payments__amount', filter=_confirmed_payment_filter()),
                money_zero,
            )
        )
        # Per-row count of currently-overdue invoices -- not summed, so the
        # CF-inclusive outstanding_expression() is correct here (see defaulters()).
        defaulters_count = paid_qs.annotate(
            outstanding=outstanding_expression()
        ).filter(
            outstanding__gt=0,
            due_date__lt=timezone.localdate(),
            status__in=['unpaid', 'partial', 'overdue'],
        ).count()

        # Top Unpaid Classes -- same separate-query pattern as class_report()
        # above, for the same Sum-with-join fan-out reason.
        expected_by_classroom = {
            row['student__classroom__id']: row
            for row in (
                qs.values('student__classroom__id', 'student__classroom__name')
                .annotate(expected_total=Coalesce(Sum(gross_due_expression()), money_zero))
            )
        }
        collected_rows = (
            Payment.objects.filter(
                student_fee__in=qs,
                status__in=CONFIRMED_PAYMENT_STATUSES,
            )
            .values('student_fee__student__classroom_id')
            .annotate(collected_total=Coalesce(Sum('amount'), money_zero))
        )
        collected_by_classroom = {
            row['student_fee__student__classroom_id']: row['collected_total']
            for row in collected_rows
        }
        class_report_rows = []
        for cid, row in expected_by_classroom.items():
            expected = row['expected_total']
            collected = collected_by_classroom.get(cid, Decimal('0.00'))
            outstanding = expected - collected
            if outstanding > 0:
                class_report_rows.append({
                    'student__classroom__id': cid,
                    'student__classroom__name': row['student__classroom__name'],
                    'expected_total': expected,
                    'collected_total': collected,
                    'outstanding': outstanding,
                })
        class_report_rows.sort(key=lambda r: -r['outstanding'])
        class_report_rows = class_report_rows[:5]

        payments_qs = Payment.objects.filter(tenant=getattr(request.user, 'tenant', None))
        if getattr(request.user, 'is_superuser', False) and not getattr(request.user, 'tenant', None):
            payments_qs = Payment.objects.all()
        recent_payments = payments_qs.select_related(
            'student',
            'student__classroom',
            'student_fee',
            'receipt',
            'recorded_by',
        ).order_by('-created_at')[:10]

        return Response({
            **summary,
            'defaulters_count': defaulters_count,
            'top_classes': class_report_rows,
            'recent_payments': PaymentSerializer(recent_payments, many=True).data,
        })