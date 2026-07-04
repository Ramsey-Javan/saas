from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum, Value, Count
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsSchoolAdmin
from accounts.models import CustomUser
from finance.models import FeeStructure, Payment, StudentFee, CONFIRMED_PAYMENT_STATUSES
from students.models import Admission, Student, Classroom

from .models import SchoolEvent
from .serializers import SchoolEventSerializer


TERM_ORDER = {
    'term1': 1,
    'term2': 2,
    'term3': 3,
    'annual': 4,
}


def _month_bounds(now_local):
    start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)

    if start.month == 1:
        last_month_start = start.replace(year=start.year - 1, month=12)
    else:
        last_month_start = start.replace(month=start.month - 1)
    last_month_end = start
    return start, next_month, last_month_start, last_month_end


def _percentage_change(current, previous):
    if not previous:
        return 0
    return round(((current - previous) / previous) * 100, 2)


def _current_term(tenant):
    structures = FeeStructure.objects.filter(tenant=tenant, is_active=True)
    if not structures.exists():
        return None
    latest = max(
        structures,
        key=lambda s: (s.academic_year, TERM_ORDER.get(s.term, 0)),
    )
    return latest.term, latest.academic_year


def _get_time_range_bounds(time_range, now_local):
    if time_range == '7d':
        return now_local - timedelta(days=7), now_local
    elif time_range == '30d':
        return now_local - timedelta(days=30), now_local
    elif time_range == 'term':
        return now_local.replace(day=1), now_local
    elif time_range == 'year':
        return now_local.replace(month=1, day=1), now_local
    else:
        return now_local - timedelta(days=30), now_local


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def dashboard_stats(request):
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'detail': 'Tenant required.'}, status=403)

    time_range = request.query_params.get('time_range', '30d')
    tz = ZoneInfo('Africa/Nairobi')
    now_local = timezone.now().astimezone(tz)
    this_month_start, next_month_start, last_month_start, last_month_end = _month_bounds(now_local)

    this_month_start_date = this_month_start.date()
    next_month_start_date = next_month_start.date()
    last_month_start_date = last_month_start.date()
    last_month_end_date = last_month_end.date()

    total_students = Student.objects.filter(tenant=tenant, is_active=True).count()
    total_teachers = CustomUser.objects.filter(tenant=tenant, role='teacher').count()

    term_info = _current_term(tenant)

    money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))

    # ── BUG FIX (corrected): total_revenue must be paid_amount + credit, not
    # paid_amount alone. When a payment exceeds what's due on an invoice,
    # recalculate_student_fees() (finance/utils.py) caps paid_amount at the
    # amount due and stashes the surplus in `credit` on the last invoice in
    # a student's chain. That credit is REAL, CONFIRMED cash already
    # received -- summing only paid_amount silently excluded it, making
    # "Total Revenue" read lower than the sum of actual confirmed payments
    # (same root cause as the Bursar Dashboard "Collected" bug -- see
    # finance/views/fees.py dashboard_summary()/term_summary()).
    student_fee_qs = StudentFee.objects.filter(tenant=tenant)
    if term_info:
        term, academic_year = term_info
        student_fee_qs = student_fee_qs.filter(
            fee_structure__term=term,
            fee_structure__academic_year=academic_year,
        )
    revenue_totals = student_fee_qs.aggregate(
        paid_amount_total=Coalesce(Sum('paid_amount'), money_zero),
        credit_total=Coalesce(Sum('credit'), money_zero),
    )
    total_revenue = revenue_totals['paid_amount_total'] + revenue_totals['credit_total']
    # ── END BUG FIX ──

    pending_qs = StudentFee.objects.filter(
        tenant=tenant,
        status__in=['unpaid', 'partial', 'overdue'],
    ).annotate(
        paid_total=Coalesce(
            Sum('payments__amount', filter=Q(payments__status='completed')),
            money_zero,
        ),
    ).annotate(
        balance_due=ExpressionWrapper(
            F('expected_amount') + F('carried_forward') + F('penalty_amount') - F('waived_amount') - F('paid_total'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )

    # ── BUG FIX: pending_fees must NOT sum balance_due (which includes
    # carried_forward) across multiple invoices. carried_forward is a
    # snapshot of a PREVIOUS term's own unpaid balance -- if both the old
    # and new term's invoices are still open, summing balance_due counts
    # that same arrears twice. This is the exact anti-pattern documented on
    # outstanding_expression() in finance/views/mixins.py, and it's why
    # "Pending Fees" here didn't match the Bursar Dashboard's "Outstanding"
    # figure, which correctly avoids carried_forward when summing (see
    # raw_expected_expression() / dashboard_summary() in finance/views/fees.py).
    #
    # Fix: derive pending_fees the same CF-free way Bursar does --
    # sum(expected_amount + penalty_amount) - sum(waived_amount) - sum(paid_amount + credit),
    # across ALL of the tenant's invoices (not just the unpaid/partial/overdue
    # subset), since that matches what "Outstanding" represents school-wide.
    # credit is included alongside paid_amount for the same reason as
    # total_revenue above: it's confirmed cash already received, just not
    # yet applied to a specific invoice's due amount.
    pending_totals = StudentFee.objects.filter(tenant=tenant).aggregate(
        raw_expected=Coalesce(
            Sum(
                ExpressionWrapper(
                    F('expected_amount') + F('penalty_amount'),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            money_zero,
        ),
        total_waived=Coalesce(Sum('waived_amount'), money_zero),
        total_paid=Coalesce(Sum('paid_amount'), money_zero),
        total_credit=Coalesce(Sum('credit'), money_zero),
    )
    pending_fees = (
        pending_totals['raw_expected']
        - pending_totals['total_waived']
        - pending_totals['total_paid']
        - pending_totals['total_credit']
    )
    # ── END BUG FIX ──

    admissions_this_month = Admission.objects.filter(
        student__tenant=tenant,
        admission_date__gte=this_month_start_date,
        admission_date__lt=next_month_start_date,
    ).count()
    admissions_last_month = Admission.objects.filter(
        student__tenant=tenant,
        admission_date__gte=last_month_start_date,
        admission_date__lt=last_month_end_date,
    ).count()

    teachers_this_month = CustomUser.objects.filter(
        tenant=tenant,
        role='teacher',
        created_at__gte=this_month_start,
        created_at__lt=next_month_start,
    ).count()
    teachers_last_month = CustomUser.objects.filter(
        tenant=tenant,
        role='teacher',
        created_at__gte=last_month_start,
        created_at__lt=last_month_end,
    ).count()

    # ── BUG FIX: Revenue this/last month using capped paid_amount, not raw Payment.amount ──
    # We approximate by looking at StudentFee records that had payments this month.
    # For true daily granularity we'd need a payment ledger, but this prevents
    # the overpayment inflation bug.
    # ── BUG FIX (corrected): include credit alongside paid_amount, same
    # reasoning as total_revenue above -- confirmed overpayment cash stored
    # in `credit` was being excluded, understating monthly revenue too.
    revenue_this_month = student_fee_qs.filter(
        updated_at__gte=this_month_start,
        updated_at__lt=next_month_start,
    ).filter(Q(paid_amount__gt=0) | Q(credit__gt=0)).aggregate(
        total=Coalesce(Sum(F('paid_amount') + F('credit'), output_field=DecimalField(max_digits=12, decimal_places=2)), money_zero)
    ).get('total')

    revenue_last_month = student_fee_qs.filter(
        updated_at__gte=last_month_start,
        updated_at__lt=last_month_end,
    ).filter(Q(paid_amount__gt=0) | Q(credit__gt=0)).aggregate(
        total=Coalesce(Sum(F('paid_amount') + F('credit'), output_field=DecimalField(max_digits=12, decimal_places=2)), money_zero)
    ).get('total')
    # ── END BUG FIX ──

    # ── BUG FIX: same carried_forward double-counting issue as pending_fees
    # above -- these were summing balance_due (CF-inclusive) across invoices
    # created in a given month. Use the same CF-free aggregate, scoped by
    # created_at, so the trend comparison is internally consistent with the
    # headline pending_fees figure.
    def _pending_total_for_range(start, end):
        totals = StudentFee.objects.filter(
            tenant=tenant,
            created_at__gte=start,
            created_at__lt=end,
        ).aggregate(
            raw_expected=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F('expected_amount') + F('penalty_amount'),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
                money_zero,
            ),
            total_waived=Coalesce(Sum('waived_amount'), money_zero),
            total_paid=Coalesce(Sum('paid_amount'), money_zero),
            total_credit=Coalesce(Sum('credit'), money_zero),
        )
        return (
            totals['raw_expected']
            - totals['total_waived']
            - totals['total_paid']
            - totals['total_credit']
        )

    pending_this_month = _pending_total_for_range(this_month_start, next_month_start)
    pending_last_month = _pending_total_for_range(last_month_start, last_month_end)
    # ── END BUG FIX ──

    # Payment status breakdown
    # ── BUG FIX: same missing-credit issue as total_revenue/pending_fees
    # above. total_paid alone excludes confirmed overpayment cash sitting
    # in `credit`, which made this section's "Total Amount" (sum of all
    # status balances) disagree with the Bursar Dashboard's Outstanding.
    payment_status = StudentFee.objects.filter(tenant=tenant).values('status').annotate(
        count=Count('id'),
        total_expected=Coalesce(Sum('expected_amount'), money_zero),
        total_paid=Coalesce(Sum('paid_amount'), money_zero),
        total_credit=Coalesce(Sum('credit'), money_zero),
        total_waived=Coalesce(Sum('waived_amount'), money_zero),
    ).order_by('status')

    payment_status_data = []
    for ps in payment_status:
        balance = (
            (ps['total_expected'] or 0)
            - (ps['total_paid'] or 0)
            - (ps['total_credit'] or 0)
            - (ps['total_waived'] or 0)
        )
        payment_status_data.append({
            'name': ps['status'],
            'value': ps['count'],
            'amount': float(max(balance, 0)),
        })
    # ── END BUG FIX ──

    # Enrollment by grade
    enrollment_by_grade = Classroom.objects.filter(tenant=tenant).annotate(
        count=Count('students', filter=Q(students__is_active=True))
    ).values('grade_level', 'count').order_by('grade_level')

    enrollment_data = []
    for e in enrollment_by_grade:
        enrollment_data.append({
            'grade': e['grade_level'],
            'count': e['count'],
        })

    # ── BUG FIX: "expected" was a placeholder heuristic (collected * 1.1),
    # not a real figure -- it could never match the true Total Expected
    # shown on the Bursar Dashboard, and would mislead anyone reading the
    # chart (e.g. in a demo). Fix: "expected" is now the true term-wide
    # total (expected_amount + penalty_amount - waived_amount, summed
    # across ALL of the current term's invoices, matching the Bursar
    # Dashboard's Net Collectible) -- the same flat figure every month,
    # since the whole term's invoices exist from day one regardless of
    # when payments trickle in. Only "collected" varies month to month.
    term_expected_totals = student_fee_qs.aggregate(
        raw_expected=Coalesce(
            Sum(
                ExpressionWrapper(
                    F('expected_amount') + F('penalty_amount'),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            money_zero,
        ),
        total_waived=Coalesce(Sum('waived_amount'), money_zero),
    )
    term_wide_expected = term_expected_totals['raw_expected'] - term_expected_totals['total_waived']

    range_start, range_end = _get_time_range_bounds(time_range, now_local)
    fee_trends = student_fee_qs.filter(
        updated_at__gte=range_start,
        updated_at__lte=range_end,
    ).filter(Q(paid_amount__gt=0) | Q(credit__gt=0)).annotate(
        month=TruncMonth('updated_at')
    ).values('month').annotate(
        collected=Coalesce(
            Sum(
                ExpressionWrapper(
                    F('paid_amount') + F('credit'),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            money_zero,
        ),
    ).order_by('month')
    # ── END BUG FIX ──

    fee_trends_data = []
    for ft in fee_trends:
        fee_trends_data.append({
            'label': ft['month'].strftime('%b'),
            'collected': float(ft['collected'] or 0),
            'expected': float(term_wide_expected or 0),
        })

    # Top defaulters
    top_defaulters = pending_qs.order_by('-balance_due')[:5]

    defaulters_data = []
    for d in top_defaulters:
        eff_balance = (d.expected_amount or 0) + (d.carried_forward or 0) + (d.penalty_amount or 0) - (d.waived_amount or 0) - (d.paid_total or 0)
        days_overdue = 0
        if d.due_date:
            days_overdue = (now_local.date() - d.due_date).days
            if days_overdue < 0:
                days_overdue = 0

        defaulters_data.append({
            'id': d.student.id,
            'name': d.student.get_full_name(),
            'admission_number': d.student.admission_number,
            'classroom': str(d.student.classroom) if d.student.classroom else 'No class',
            'balance': float(max(eff_balance, 0)),
            'days_overdue': days_overdue,
        })

    # ───────────────────────────────────────────────────────────
    # RECENT ACTIVITY — safe fallback if ActivityLog table missing
    # ───────────────────────────────────────────────────────────
    activity = []
    try:
        from activity.models import ActivityLog

        recent_logs = ActivityLog.objects.filter(tenant=tenant).select_related('actor')[:25]

        for log in recent_logs:
            activity.append({
                'id': str(log.id),
                'type': log.activity_type,
                'title': log.title,
                'description': log.description,
                'actor': log.actor.get_full_name() if log.actor else 'System',
                'target_name': log.target_name,
                'timestamp': log.created_at.astimezone(tz).isoformat(),
                'metadata': log.metadata,
            })
    except Exception:
        pass

    return Response({
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_revenue': float(total_revenue or 0),
        'pending_fees': float(pending_fees or 0),
        'students_change': _percentage_change(admissions_this_month, admissions_last_month),
        'teachers_change': _percentage_change(teachers_this_month, teachers_last_month),
        'revenue_change': _percentage_change(float(revenue_this_month or 0), float(revenue_last_month or 0)),
        'pending_change': _percentage_change(float(pending_this_month or 0), float(pending_last_month or 0)),
        'recent_activity': activity,
        'payment_status': payment_status_data,
        'enrollment_by_grade': enrollment_data,
        'fee_trends': fee_trends_data,
        'defaulters': defaulters_data,
    })


class SchoolEventViewSet(viewsets.ModelViewSet):
    """Manual calendar events for the Upcoming Events dashboard widget."""
    serializer_class = SchoolEventSerializer
    permission_classes = [IsSchoolAdmin]

    def get_queryset(self):
        return SchoolEvent.objects.filter(tenant=self.request.user.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)


# ───────────────────────────────────────────────────────────────────────
# UPCOMING EVENTS — merges manually-created SchoolEvent rows with
# auto-computed deadlines derived from existing data (fee due dates, exam
# start dates, report card generation windows). WaiverPolicy has no date
# field, so "waiver deadlines" can only ever be manual SchoolEvent entries
# — there's nothing to auto-compute there.
# ───────────────────────────────────────────────────────────────────────

EVENT_TYPE_META = {
    'fee': {'color': 'bg-red-50 text-red-600', 'action': '/finance/defaulters'},
    'exam': {'color': 'bg-purple-50 text-purple-600', 'action': '/academics/exams'},
    'report_card': {'color': 'bg-green-50 text-green-600', 'action': '/academics/report-cards'},
    'event': {'color': 'bg-blue-50 text-blue-600', 'action': '/communication'},
    'meeting': {'color': 'bg-blue-50 text-blue-600', 'action': '/communication'},
    'holiday': {'color': 'bg-gray-50 text-gray-600', 'action': None},
    'deadline': {'color': 'bg-orange-50 text-orange-600', 'action': None},
    'other': {'color': 'bg-gray-50 text-gray-600', 'action': None},
}


def _event_payload(id_, title, date_, type_, source, extra_action=None):
    meta = EVENT_TYPE_META.get(type_, EVENT_TYPE_META['other'])
    return {
        'id': id_,
        'title': title,
        'date': date_.isoformat() if hasattr(date_, 'isoformat') else date_,
        'type': type_,
        'color': meta['color'],
        'action': extra_action or meta['action'],
        'source': source,  # 'manual' | 'auto' — lets the frontend distinguish editable vs derived
    }


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def upcoming_events(request):
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'detail': 'Tenant required.'}, status=403)

    today = timezone.localdate()
    horizon = today + timedelta(days=60)  # don't show anything more than ~2 months out
    events = []

    # ── Manual events ──────────────────────────────────────────────
    manual = SchoolEvent.objects.filter(tenant=tenant, date__gte=today, date__lte=horizon)
    for e in manual:
        events.append(_event_payload(f'manual-{e.id}', e.title, e.date, e.category, 'manual'))

    # ── Nearest upcoming fee due date(s) ───────────────────────────
    fee_dates = (
        FeeStructure.objects.filter(tenant=tenant, is_active=True, due_date__gte=today, due_date__lte=horizon)
        .values_list('due_date', flat=True)
        .distinct()
        .order_by('due_date')[:3]
    )
    for due_date in fee_dates:
        events.append(_event_payload(
            f'fee-due-{due_date}', 'Fee Payment Deadline', due_date, 'fee', 'auto',
        ))

    # ── Nearest upcoming exam start date(s) ────────────────────────
    try:
        from academics.models import ExamSetup

        exams = (
            ExamSetup.objects.filter(tenant=tenant, is_active=True, start_date__gte=today, start_date__lte=horizon)
            .order_by('start_date')[:5]
        )
        for exam in exams:
            events.append(_event_payload(
                f'exam-{exam.id}', f'{exam.name} Begins', exam.start_date, 'exam', 'auto',
                extra_action=f'/academics/exams/{exam.id}',
            ))
    except Exception:
        pass

    # ── Report card windows ────────────
    try:
        from academics.models import ReportCard

        upcoming_report_dates = (
            ReportCard.objects.filter(
                tenant=tenant,
                status='draft',
                next_term_opening_date__gte=today,
                next_term_opening_date__lte=horizon,
            )
            .values_list('next_term_opening_date', flat=True)
            .distinct()
            .order_by('next_term_opening_date')[:2]
        )
        for d in upcoming_report_dates:
            events.append(_event_payload(
                f'report-cards-{d}', 'Report Cards Due', d, 'report_card', 'auto',
            ))
    except Exception:
        pass

    events.sort(key=lambda e: e['date'])
    return Response(events[:8])