from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsSchoolAdmin
from accounts.models import CustomUser
from finance.models import FeeStructure, Payment, StudentFee
from students.models import Admission, Student


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


@api_view(['GET'])
@permission_classes([IsSchoolAdmin])
def dashboard_stats(request):
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'detail': 'Tenant required.'}, status=403)

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
    from django.db.models import Sum as DSum

    pending_qs = StudentFee.objects.filter(
        tenant=tenant,
        status__in=['unpaid', 'partial', 'overdue'],
    ).annotate(
        paid_total=Coalesce(
            Sum('payments__amount', filter=Q(payments__status='completed')),
            money_zero,
        ),
    ).annotate(
        effective_balance=ExpressionWrapper(
            F('expected_amount') + F('carried_forward') + F('penalty_amount') - F('waived_amount') - F('paid_total'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )

    pending_fees = pending_qs.aggregate(
        total=Coalesce(DSum('effective_balance'), money_zero)
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
    ).aggregate(total=Coalesce(Sum('effective_balance'), money_zero)).get('total')

    pending_last_month = pending_qs.filter(
        created_at__gte=last_month_start,
        created_at__lt=last_month_end,
    ).aggregate(total=Coalesce(Sum('effective_balance'), money_zero)).get('total')

    admissions = Admission.objects.filter(student__tenant=tenant).select_related('student').order_by('-admission_date')[:10]
    payments = Payment.objects.filter(tenant=tenant, status='completed').select_related('student').order_by('-created_at')[:10]
    transfers = Student.objects.filter(tenant=tenant, status=Student.Status.TRANSFERRED).select_related('classroom').order_by('-updated_at')[:10]

    activity = []
    for admission in admissions:
        activity.append({
            'type': 'admission',
            'description': f"{admission.student.get_full_name()} admitted to {admission.class_admitted}",
            'timestamp': datetime.combine(admission.admission_date, datetime.min.time(), tzinfo=tz).isoformat(),
        })
    for payment in payments:
        activity.append({
            'type': 'payment',
            'description': f"Payment received from {payment.student.get_full_name()} (KES {payment.amount:,.2f})",
            'timestamp': payment.created_at.astimezone(tz).isoformat(),
        })
    for student in transfers:
        activity.append({
            'type': 'transfer',
            'description': f"{student.get_full_name()} transferred to {student.classroom or 'new class'}",
            'timestamp': student.updated_at.astimezone(tz).isoformat(),
        })

    activity = sorted(activity, key=lambda item: item['timestamp'], reverse=True)[:10]

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
    })
