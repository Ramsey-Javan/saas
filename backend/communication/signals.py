from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='academics.AttendanceSession')
def on_attendance_session_locked(sender, instance, **kwargs):
    if instance.is_locked:
        from .tasks import send_attendance_alert_task

        transaction.on_commit(lambda: send_attendance_alert_task.delay(str(instance.id), instance.tenant_id))


@receiver(post_save, sender='academics.ReportCard')
def on_report_card_published(sender, instance, **kwargs):
    if instance.status == 'published' and instance.published_at:
        from .tasks import send_report_card_notification_task

        transaction.on_commit(lambda: send_report_card_notification_task.delay(str(instance.id), instance.tenant_id))
