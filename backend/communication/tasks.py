from datetime import datetime, timedelta

import pytz
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from tenants.models import Tenant


@shared_task
def dispatch_announcement_task(announcement_id: str, tenant_id: int, sent_by_id: int = None):
    from accounts.models import CustomUser
    from .models import Announcement
    from .services import AnnouncementDispatcher

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        return None
    announcement = Announcement.objects.filter(id=announcement_id, tenant=tenant).first()
    if not announcement:
        return None
    sent_by = CustomUser.objects.filter(id=sent_by_id).first() if sent_by_id else None
    return AnnouncementDispatcher().dispatch(announcement, tenant, sent_by=sent_by)


@shared_task
def send_fee_reminders_task():
    from finance.models import StudentFee
    from .models import MessageLog
    from .services import SMSService

    today = timezone.localdate()
    sms = SMSService()
    for tenant in Tenant.objects.filter(is_active=True):
        overdue = StudentFee.objects.filter(
            tenant=tenant,
            status__in=['unpaid', 'partial', 'overdue'],
            due_date__lt=today,
        ).select_related('student__primary_guardian', 'fee_structure')
        for invoice in overdue:
            guardian = invoice.student.primary_guardian
            if not guardian or not guardian.phone or invoice.balance <= 0:
                continue
            message = (
                f'Dear {guardian.first_name}, {invoice.student.get_full_name()} '
                f'({invoice.student.admission_number}) has an outstanding fee balance of '
                f'KES {invoice.balance:,.2f} for {invoice.fee_structure.term} '
                f'{invoice.fee_structure.academic_year}. Please clear the balance. '
                f"Pay via M-Pesa Paybill {settings.MPESA.get('SHORTCODE', '')} "
                f'Account: {invoice.student.admission_number}.'
            )
            log = MessageLog.objects.create(
                tenant=tenant,
                channel='sms',
                recipient_user=getattr(guardian, 'user', None),
                recipient_phone=guardian.phone,
                recipient_name=guardian.full_name,
                message_body=message,
                status='pending',
            )
            try:
                sms.send([guardian.phone], message)
                log.status = 'sent'
            except Exception as exc:
                log.status = 'failed'
                log.failure_reason = str(exc)
            log.save()


@shared_task
def send_attendance_alert_task(session_id: str, tenant_id: int):
    from academics.models import AttendanceSession
    from .models import MessageLog
    from .services import SMSService

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        return None
    session = AttendanceSession.objects.filter(id=session_id, tenant=tenant).select_related('classroom').first()
    if not session:
        return None
    sms = SMSService()
    absent_records = session.records.filter(status='A').select_related('student__primary_guardian__user')
    for record in absent_records:
        guardian = record.student.primary_guardian
        if not guardian or not guardian.phone:
            continue
        message = (
            f'Dear {guardian.first_name}, {record.student.get_full_name()} '
            f'({record.student.admission_number}) was marked absent on '
            f"{session.date.strftime('%d %b %Y')}. Please contact the school if this is unexpected."
        )
        log = MessageLog.objects.create(
            tenant=tenant,
            channel='sms',
            recipient_user=getattr(guardian, 'user', None),
            recipient_phone=guardian.phone,
            recipient_name=guardian.full_name,
            message_body=message,
        )
        try:
            sms.send([guardian.phone], message)
            log.status = 'sent'
        except Exception as exc:
            log.status = 'failed'
            log.failure_reason = str(exc)
        log.save()


@shared_task
def send_report_card_notification_task(report_card_id: str, tenant_id: int):
    from academics.models import ReportCard
    from .models import InAppNotification, MessageLog
    from .services import PushNotificationService, SMSService

    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        return None
    report_card = ReportCard.objects.filter(id=report_card_id, tenant=tenant).select_related(
        'student__primary_guardian__user', 'classroom'
    ).first()
    if not report_card:
        return None
    guardian = report_card.student.primary_guardian
    guardian_user = getattr(guardian, 'user', None)
    title = 'Report Card Available'
    body = (
        f"{report_card.student.get_full_name()}'s {report_card.term} "
        f'{report_card.academic_year} report card is now available.'
    )
    if guardian_user:
        InAppNotification.objects.create(
            tenant=tenant,
            user=guardian_user,
            title=title,
            body=body,
            type='report_card',
            action_url=f'/academics/report-cards/{report_card.id}',
        )
        try:
            PushNotificationService().send_to_user(guardian_user, title, body, url=f'/academics/report-cards/{report_card.id}')
        except Exception:
            pass
    if guardian and guardian.phone:
        log = MessageLog.objects.create(
            tenant=tenant,
            channel='sms',
            recipient_user=guardian_user,
            recipient_phone=guardian.phone,
            recipient_name=guardian.full_name,
            message_body=body,
        )
        try:
            SMSService().send([guardian.phone], body)
            log.status = 'sent'
        except Exception as exc:
            log.status = 'failed'
            log.failure_reason = str(exc)
        log.save()


@shared_task
def process_scheduled_task():
    from .models import Announcement

    now = timezone.now()
    due = Announcement.objects.filter(
        status='scheduled',
        send_immediately=False,
        scheduled_at__lte=now,
        is_recurring=False,
    ).select_related('tenant')
    for announcement in due:
        dispatch_announcement_task.delay(str(announcement.id), announcement.tenant_id, announcement.sent_by_id)


@shared_task
def process_recurring_task():
    from .models import Announcement

    now = timezone.now()
    due = Announcement.objects.filter(
        status__in=['scheduled', 'sent'],
        is_recurring=True,
        next_run_at__lte=now,
    ).select_related('tenant')
    for announcement in due:
        clone = Announcement.objects.create(
            tenant=announcement.tenant,
            title=announcement.title,
            body=announcement.body,
            template=announcement.template,
            template_vars=announcement.template_vars,
            channels=announcement.channels,
            recipient_type=announcement.recipient_type,
            recipient_class=announcement.recipient_class,
            recipient_grade=announcement.recipient_grade,
            recipient_user=announcement.recipient_user,
            send_immediately=True,
            status='scheduled',
            is_recurring=False,
        )
        dispatch_announcement_task.delay(str(clone.id), clone.tenant_id, announcement.sent_by_id)
        announcement.next_run_at = calculate_next_run(announcement.recurrence_rule, now)
        announcement.save(update_fields=['next_run_at'])


def calculate_next_run(rule: dict, from_dt):
    nairobi = pytz.timezone('Africa/Nairobi')
    frequency = rule.get('frequency', 'weekly')
    time_str = rule.get('time', '08:00')
    hour, minute = map(int, time_str.split(':'))
    now_local = from_dt.astimezone(nairobi)

    if frequency == 'daily':
        next_run = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=1)
    elif frequency == 'weekly':
        day_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6,
        }
        target_day = day_map.get(rule.get('day', 'monday'), 0)
        days_ahead = target_day - now_local.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_run = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
    elif frequency == 'monthly':
        day = min(int(rule.get('day_of_month', 1)), 28)
        year = now_local.year + 1 if now_local.month == 12 else now_local.year
        month = 1 if now_local.month == 12 else now_local.month + 1
        next_run = now_local.replace(year=year, month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
    else:
        next_run = now_local + timedelta(days=7)

    return next_run.astimezone(pytz.utc)
