import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_fee_reminder_sms(self, student_id, term, academic_year, balance):
    """Send a fee balance reminder SMS to a student's parent."""
    try:
        from apps.students.models import Student
        from apps.notifications.africastalking import AfricasTalkingService

        student = Student.objects.get(pk=student_id)
        phone = student.parent_phone
        if not phone:
            logger.warning('Student %s has no parent phone number', student_id)
            return {'status': 'skipped', 'reason': 'No parent phone'}

        message = (
            f'Dear {student.parent_name}, this is a reminder that {student.full_name} '
            f'has an outstanding fee balance of KES {balance:,.2f} '
            f'for {term.replace("term", "Term ")} {academic_year}. '
            f'Please clear the balance to avoid disruption of studies. Thank you.'
        )

        service = AfricasTalkingService()
        logs = service.send_sms_and_log(phone, message, student=student)
        return {'status': 'sent', 'sms_log_ids': [log.id for log in logs]}

    except Exception as exc:
        logger.error('fee reminder SMS failed for student %s: %s', student_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_attendance_sms(self, student_id, date, attendance_status):
    """Notify a parent when their child is marked absent."""
    try:
        from apps.students.models import Student
        from apps.notifications.africastalking import AfricasTalkingService

        student = Student.objects.get(pk=student_id)
        phone = student.parent_phone
        if not phone:
            return {'status': 'skipped', 'reason': 'No parent phone'}

        status_display = {
            'absent': 'absent',
            'late': 'late',
            'excused': 'absent (excused)',
        }.get(attendance_status, attendance_status)

        message = (
            f'Dear {student.parent_name}, {student.full_name} was marked {status_display} '
            f'on {date}. Please contact the school if you have any concerns.'
        )

        service = AfricasTalkingService()
        logs = service.send_sms_and_log(phone, message, student=student)
        return {'status': 'sent', 'sms_log_ids': [log.id for log in logs]}

    except Exception as exc:
        logger.error('Attendance SMS failed for student %s: %s', student_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_bulk_sms(self, phone_numbers, message, student_ids=None, sent_by_id=None):
    """
    Send a bulk SMS to a list of phone numbers.

    Args:
        phone_numbers: list of phone number strings
        message: SMS message body
        student_ids: optional list of student PKs (must align with phone_numbers)
        sent_by_id: optional user PK for attribution
    """
    try:
        from apps.notifications.africastalking import AfricasTalkingService
        from django.contrib.auth import get_user_model

        User = get_user_model()
        sent_by = None
        if sent_by_id:
            try:
                sent_by = User.objects.get(pk=sent_by_id)
            except User.DoesNotExist:
                pass

        service = AfricasTalkingService()
        logs = service.send_sms_and_log(phone_numbers, message, sent_by=sent_by)
        return {
            'status': 'completed',
            'total': len(phone_numbers),
            'sent': sum(1 for log in logs if log.status == 'sent'),
            'failed': sum(1 for log in logs if log.status == 'failed'),
            'sms_log_ids': [log.id for log in logs],
        }

    except Exception as exc:
        logger.error('Bulk SMS task failed: %s', exc)
        raise self.retry(exc=exc)
