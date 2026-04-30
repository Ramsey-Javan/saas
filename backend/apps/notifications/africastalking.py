import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class AfricasTalkingService:
    def __init__(self):
        self.username = settings.AT_USERNAME
        self.api_key = settings.AT_API_KEY
        self.sender_id = settings.AT_SENDER_ID or None
        self._gateway = None

    def _get_sms_service(self):
        if self._gateway is None:
            import africastalking
            africastalking.initialize(self.username, self.api_key)
            self._gateway = africastalking.SMS
        return self._gateway

    def send_sms(self, phone_numbers, message):
        """
        Send SMS to one or more recipients.

        Args:
            phone_numbers: str or list of str in E.164 format (e.g. +254712345678)
            message: str message body

        Returns:
            dict with AT API response
        """
        if isinstance(phone_numbers, str):
            phone_numbers = [phone_numbers]

        # Normalize numbers to E.164
        normalized = []
        for phone in phone_numbers:
            p = str(phone).strip().replace(' ', '')
            if not p.startswith('+'):
                if p.startswith('0'):
                    p = '+254' + p[1:]
                elif p.startswith('254'):
                    p = '+' + p
                else:
                    p = '+' + p
            normalized.append(p)

        sms = self._get_sms_service()
        kwargs = {'message': message, 'recipients': normalized}
        if self.sender_id:
            kwargs['senderId'] = self.sender_id

        try:
            response = sms.send(**kwargs)
            logger.info('SMS sent to %s: %s', normalized, response)
            return response
        except Exception as exc:
            logger.error('Africa\'s Talking SMS failed for %s: %s', normalized, exc)
            raise

    def send_sms_and_log(self, phone_numbers, message, student=None, sent_by=None):
        """Send SMS and save to SMSLog. Returns list of SMSLog instances."""
        from apps.notifications.models import SMSLog

        if isinstance(phone_numbers, str):
            phone_numbers = [phone_numbers]

        logs = []
        try:
            response = self.send_sms(phone_numbers, message)
            recipients = response.get('SMSMessageData', {}).get('Recipients', [])
            receipt_map = {r.get('number'): r for r in recipients}

            for phone in phone_numbers:
                p_norm = phone if phone.startswith('+') else '+254' + phone.lstrip('0')
                receipt = receipt_map.get(p_norm, {})
                sms_status = receipt.get('status', 'Unknown')
                log = SMSLog.objects.create(
                    recipient_phone=phone,
                    message=message,
                    student=student,
                    sent_by=sent_by,
                    status='sent' if 'Success' in sms_status else 'failed',
                    sent_at=timezone.now(),
                    provider_response=receipt,
                    message_id=receipt.get('messageId', ''),
                )
                logs.append(log)
        except Exception as exc:
            for phone in phone_numbers:
                log = SMSLog.objects.create(
                    recipient_phone=phone,
                    message=message,
                    student=student,
                    sent_by=sent_by,
                    status='failed',
                    provider_response={'error': str(exc)},
                )
                logs.append(log)

        return logs
