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
from finance.models import FeeStructure, Payment, StudentFee
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
    revenue_qs = Payment.objects.filter(tenant=tenant, status='completed')
    if term_info:
        term, academic_year = term_info
        revenue_qs = revenue_qs.filter(
            student_fee__fee_structure__term=term,
            student_fee__fee_structure__academic_year=academic_year,
        )
    total_revenue = revenue_qs.aggregate(
        total=Coalesce(Sum('amount'), Value(Decimal('0.00')))
    ).get('total')

    money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))

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

    pending_fees = pending_qs.aggregate(
        total=Coalesce(Sum('balance_due'), money_zero)
    ).get('total')

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

    revenue_this_month = Payment.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__gte=this_month_start,
        created_at__lt=next_month_start,
    ).aggregate(total=Coalesce(Sum('amount'), Value(Decimal('0.00')))).get('total')

    revenue_last_month = Payment.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__gte=last_month_start,
        created_at__lt=last_month_end,
    ).aggregate(total=Coalesce(Sum('amount'), Value(Decimal('0.00')))).get('total')

    pending_this_month = pending_qs.filter(
        created_at__gte=this_month_start,
        created_at__lt=next_month_start,
    ).aggregate(total=Coalesce(Sum('balance_due'), money_zero)).get('total')

    pending_last_month = pending_qs.filter(
        created_at__gte=last_month_start,
        created_at__lt=last_month_end,
    ).aggregate(total=Coalesce(Sum('balance_due'), money_zero)).get('total')

    # Payment status breakdown
    payment_status = StudentFee.objects.filter(tenant=tenant).values('status').annotate(
        count=Count('id'),
        total_expected=Coalesce(Sum('expected_amount'), money_zero),
        total_paid=Coalesce(Sum('paid_amount'), money_zero),
        total_waived=Coalesce(Sum('waived_amount'), money_zero),
    ).order_by('status')

    payment_status_data = []
    for ps in payment_status:
        balance = (ps['total_expected'] or 0) - (ps['total_paid'] or 0) - (ps['total_waived'] or 0)
        payment_status_data.append({
            'name': ps['status'],
            'value': ps['count'],
            'amount': float(max(balance, 0)),
        })

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

    # Fee trends (monthly)
    range_start, range_end = _get_time_range_bounds(time_range, now_local)
    fee_trends = Payment.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__gte=range_start,
        created_at__lte=range_end,
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        collected=Coalesce(Sum('amount'), Value(Decimal('0.00')))
    ).order_by('month')

    fee_trends_data = []
    for ft in fee_trends:
        fee_trends_data.append({
            'label': ft['month'].strftime('%b'),
            'collected': float(ft['collected'] or 0),
            'expected': float(ft['collected'] or 0) * 1.1,
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
        # Table doesn't exist yet (migrations not run) or other DB issue
        # Fall back to empty activity list so dashboard still loads
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
    # One entry per distinct upcoming due_date among active fee structures,
    # not one per classroom, to avoid flooding the list if many classes
    # share the same due date (the common case).
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

    # ── Report card windows (best-effort: next_term_opening_date acts
    #    as the natural "reports should be ready by" marker on existing
    #    ReportCard rows for the current academic year) ────────────
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