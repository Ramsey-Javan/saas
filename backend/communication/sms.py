import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone


class AfricasTalkingService:
    """SMS sending via Africa's Talking API."""

    BASE_URL = 'https://api.africastalking.com/version1/messaging'
    SANDBOX_URL = 'https://api.sandbox.africastalking.com/version1/messaging'

    def __init__(self):
        cfg = settings.AFRICA_TALKING
        self.api_key = cfg.get('API_KEY', '')
        self.username = cfg.get('USERNAME', 'sandbox')
        self.sender_id = cfg.get('SENDER_ID', '')
        self.url = self.SANDBOX_URL if self.username == 'sandbox' else self.BASE_URL

    def send(self, recipients: list[str], message: str) -> dict:
        payload = {
            'username': self.username,
            'to': ','.join(recipients),
            'message': message,
        }
        if self.sender_id:
            payload['from'] = self.sender_id

        response = requests.post(
            self.url,
            data=payload,
            headers={
                'apiKey': self.api_key,
                'Accept': 'application/json',
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


@shared_task(bind=True, max_retries=3)
def send_sms_task(self, recipients: list, message: str, log_id: int = None):
    from communication.models import SMSLog

    try:
        result = AfricasTalkingService().send(recipients, message)

        if log_id:
            log = SMSLog.objects.get(id=log_id)
            log.status = 'sent'
            log.sent_at = timezone.now()
            recipients_data = result.get('SMSMessageData', {}).get('Recipients', [])
            if recipients_data:
                log.reference_id = recipients_data[0].get('messageId', '')
            log.save(update_fields=['status', 'sent_at', 'reference_id'])

        return result
    except Exception as exc:
        if log_id:
            try:
                log = SMSLog.objects.get(id=log_id)
                log.status = 'failed'
                log.error_message = str(exc)
                log.save(update_fields=['status', 'error_message'])
            except SMSLog.DoesNotExist:
                pass
        raise self.retry(exc=exc, countdown=60)


@shared_task
def send_fee_reminders():
    """Send reminders for pending payments using the current finance models."""
    from communication.models import SMSLog
    from finance.models import Payment

    pending_payments = Payment.objects.filter(status='pending').select_related('tenant', 'student')
    for payment in pending_payments:
        guardians = payment.student.guardians.filter(is_primary=True)
        for guardian in guardians:
            if not guardian.phone_number:
                continue

            message = (
                f'Dear {guardian.name}, payment of KES {payment.amount:,.2f} '
                f'for {payment.student.user.get_full_name()} is still pending. Thank you.'
            )
            log = SMSLog.objects.create(
                tenant=payment.tenant,
                recipient_phone=guardian.phone_number,
                message=message,
                status='pending',
                provider='africas_talking',
            )
            send_sms_task.delay([guardian.phone_number], message, log.id)
