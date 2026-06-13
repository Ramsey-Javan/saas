import json
import requests

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.utils import timezone

from accounts.models import CustomUser
from students.models import Student

from .models import Announcement, InAppNotification, MessageLog, PushSubscription


class SMSService:
    BASE_URL = 'https://api.africastalking.com/version1/messaging'
    SANDBOX_URL = 'https://api.sandbox.africastalking.com/version1/messaging'

    def __init__(self):
        self.api_key = settings.AFRICA_TALKING['API_KEY']
        self.username = settings.AFRICA_TALKING['USERNAME']
        self.sender = settings.AFRICA_TALKING.get('SENDER_ID', '')
        self.is_sandbox = self.username == 'sandbox'
        self.url = self.SANDBOX_URL if self.is_sandbox else self.BASE_URL

    def send(self, recipients: list[str], message: str) -> dict:
        payload = {
            'username': self.username,
            'to': ','.join(recipients),
            'message': message[:160],
        }
        if self.sender:
            payload['from'] = self.sender
        response = requests.post(
            self.url,
            data=payload,
            headers={'apiKey': self.api_key, 'Accept': 'application/json'},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


class WhatsAppService:
    def __init__(self):
        from twilio.rest import Client

        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.from_number = settings.TWILIO_WHATSAPP_FROM

    def send(self, to_phone: str, message: str) -> dict:
        if not to_phone.startswith('whatsapp:'):
            phone = to_phone.strip().replace(' ', '')
            if phone.startswith('0'):
                phone = f'+254{phone[1:]}'
            elif phone.startswith('254'):
                phone = f'+{phone}'
            to_phone = f'whatsapp:{phone}'
        message_obj = self.client.messages.create(body=message, from_=self.from_number, to=to_phone)
        return {'sid': message_obj.sid, 'status': message_obj.status}

    def send_bulk(self, recipients: list[str], message: str) -> list[dict]:
        results = []
        for phone in recipients:
            try:
                results.append({'phone': phone, 'success': True, **self.send(phone, message)})
            except Exception as exc:
                results.append({'phone': phone, 'success': False, 'error': str(exc)})
        return results


class EmailService:
    def send(self, recipients: list[str], subject: str, body: str, html_body: str = None) -> dict:
        sent = 0
        failed = 0
        errors = []
        for email in recipients:
            try:
                if html_body:
                    msg = EmailMultiAlternatives(subject, body, settings.DEFAULT_FROM_EMAIL, [email])
                    msg.attach_alternative(html_body, 'text/html')
                    msg.send()
                else:
                    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
                sent += 1
            except Exception as exc:
                failed += 1
                errors.append(str(exc))
        return {'sent': sent, 'failed': failed, 'errors': errors}


class PushNotificationService:
    def send_to_user(self, user, title: str, body: str, url: str = '/', icon: str = '/icons/icon-192.png') -> dict:
        from pywebpush import WebPushException, webpush

        subscriptions = PushSubscription.objects.filter(user=user, is_active=True)
        payload = json.dumps({'title': title, 'body': body, 'url': url, 'icon': icon})
        vapid_claims = {'sub': f'mailto:{settings.VAPID_CLAIMS_EMAIL}'}
        sent = 0
        failed = 0
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        'endpoint': sub.endpoint,
                        'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims=vapid_claims,
                )
                sent += 1
            except WebPushException as exc:
                failed += 1
                if '410' in str(exc) or '404' in str(exc):
                    sub.is_active = False
                    sub.save(update_fields=['is_active'])
        return {'sent': sent, 'failed': failed}

    def send_to_users(self, users, title: str, body: str, url: str = '/') -> dict:
        total = {'sent': 0, 'failed': 0}
        for user in users:
            result = self.send_to_user(user, title, body, url)
            total['sent'] += result['sent']
            total['failed'] += result['failed']
        return total


class AnnouncementDispatcher:
    def resolve_recipients(self, announcement: Announcement, tenant) -> list[dict]:
        recipients = []
        seen = set()

        def add(user=None, phone='', email='', name=''):
            key = user.id if user else phone or email or name
            if not key or key in seen:
                return
            seen.add(key)
            recipients.append({'user': user, 'phone': phone or '', 'email': email or '', 'name': name or ''})

        if announcement.recipient_type == 'class':
            students = Student.objects.filter(
                tenant=tenant,
                classroom=announcement.recipient_class,
                is_active=True,
            ).select_related('primary_guardian__user')
            for student in students:
                guardian = student.primary_guardian
                if guardian:
                    add(getattr(guardian, 'user', None), guardian.phone, guardian.email, guardian.full_name)
        elif announcement.recipient_type == 'grade':
            students = Student.objects.filter(
                tenant=tenant,
                classroom__grade_level=announcement.recipient_grade,
                is_active=True,
            ).select_related('primary_guardian__user')
            for student in students:
                guardian = student.primary_guardian
                if guardian:
                    add(getattr(guardian, 'user', None), guardian.phone, guardian.email, guardian.full_name)
        elif announcement.recipient_type == 'school':
            students = Student.objects.filter(tenant=tenant, is_active=True).select_related('primary_guardian__user')
            for student in students:
                guardian = student.primary_guardian
                if guardian:
                    add(getattr(guardian, 'user', None), guardian.phone, guardian.email, guardian.full_name)
        elif announcement.recipient_type == 'individual' and announcement.recipient_user:
            user = announcement.recipient_user
            add(user, getattr(user, 'phone_number', ''), user.email, user.get_full_name())
        elif announcement.recipient_type == 'teachers':
            for user in CustomUser.objects.filter(tenant=tenant, role='teacher', is_active=True):
                add(user, getattr(user, 'phone_number', ''), user.email, user.get_full_name())
        elif announcement.recipient_type == 'staff':
            users = CustomUser.objects.filter(
                tenant=tenant, role__in=['teacher', 'bursar', 'finance', 'admin'], is_active=True
            )
            for user in users:
                add(user, getattr(user, 'phone_number', ''), user.email, user.get_full_name())
        return recipients

    def dispatch(self, announcement: Announcement, tenant, sent_by=None) -> dict:
        announcement.status = Announcement.Status.SENDING
        announcement.save(update_fields=['status'])

        recipients = self.resolve_recipients(announcement, tenant)
        channels = announcement.channels or []
        services = {
            'sms': SMSService(),
            'email': EmailService(),
        }
        total = 0
        delivered = 0
        failed_count = 0

        for recipient in recipients:
            message_body = announcement.body
            if announcement.template:
                message_body = announcement.template.render({**announcement.template_vars, 'recipient_name': recipient['name']})

            if 'sms' in channels and recipient['phone']:
                total, delivered, failed_count = self._send_sms(
                    services['sms'], announcement, tenant, recipient, message_body, total, delivered, failed_count
                )
            if 'whatsapp' in channels and recipient['phone']:
                total, delivered, failed_count = self._send_whatsapp(
                    announcement, tenant, recipient, message_body, total, delivered, failed_count
                )
            if 'email' in channels and recipient['email']:
                subject = announcement.title
                if announcement.template and announcement.template.subject:
                    subject = announcement.template.render_subject(announcement.template_vars)
                total, delivered, failed_count = self._send_email(
                    services['email'], announcement, tenant, recipient, subject, message_body, total, delivered, failed_count
                )
            if 'inapp' in channels and recipient['user']:
                InAppNotification.objects.create(
                    tenant=tenant,
                    user=recipient['user'],
                    title=announcement.title,
                    body=message_body,
                    type=InAppNotification.NotificationType.ANNOUNCEMENT,
                    announcement=announcement,
                )
                try:
                    PushNotificationService().send_to_user(recipient['user'], announcement.title, message_body[:100])
                except Exception:
                    pass
                MessageLog.objects.create(
                    tenant=tenant,
                    announcement=announcement,
                    channel=MessageLog.Channel.INAPP,
                    recipient_user=recipient['user'],
                    recipient_name=recipient['name'],
                    message_body=message_body,
                    status=MessageLog.Status.DELIVERED,
                    delivered_at=timezone.now(),
                )
                total += 1
                delivered += 1

        announcement.status = Announcement.Status.SENT
        announcement.sent_at = timezone.now()
        announcement.sent_by = sent_by
        announcement.total_recipients = total
        announcement.delivered_count = delivered
        announcement.failed_count = failed_count
        announcement.save()
        return {'total': total, 'delivered': delivered, 'failed': failed_count}

    def _send_sms(self, service, announcement, tenant, recipient, body, total, delivered, failed_count):
        log = MessageLog.objects.create(
            tenant=tenant,
            announcement=announcement,
            channel=MessageLog.Channel.SMS,
            recipient_user=recipient['user'],
            recipient_phone=recipient['phone'],
            recipient_name=recipient['name'],
            message_body=body,
        )
        try:
            result = service.send([recipient['phone']], body)
            remote = result.get('SMSMessageData', {}).get('Recipients', [{}])[0]
            log.status = MessageLog.Status.SENT
            log.provider_message_id = remote.get('messageId', '')
            log.provider_cost = remote.get('cost', '')
            delivered += 1
        except Exception as exc:
            log.status = MessageLog.Status.FAILED
            log.failure_reason = str(exc)
            failed_count += 1
        log.save()
        return total + 1, delivered, failed_count

    def _send_whatsapp(self, announcement, tenant, recipient, body, total, delivered, failed_count):
        log = MessageLog.objects.create(
            tenant=tenant,
            announcement=announcement,
            channel=MessageLog.Channel.WHATSAPP,
            recipient_user=recipient['user'],
            recipient_phone=recipient['phone'],
            recipient_name=recipient['name'],
            message_body=body,
        )
        try:
            result = WhatsAppService().send(recipient['phone'], body)
            log.status = MessageLog.Status.SENT
            log.provider_message_id = result.get('sid', '')
            delivered += 1
        except Exception as exc:
            log.status = MessageLog.Status.FAILED
            log.failure_reason = str(exc)
            failed_count += 1
        log.save()
        return total + 1, delivered, failed_count

    def _send_email(self, service, announcement, tenant, recipient, subject, body, total, delivered, failed_count):
        log = MessageLog.objects.create(
            tenant=tenant,
            announcement=announcement,
            channel=MessageLog.Channel.EMAIL,
            recipient_user=recipient['user'],
            recipient_email=recipient['email'],
            recipient_name=recipient['name'],
            message_body=body,
        )
        try:
            service.send([recipient['email']], subject, body)
            log.status = MessageLog.Status.SENT
            delivered += 1
        except Exception as exc:
            log.status = MessageLog.Status.FAILED
            log.failure_reason = str(exc)
            failed_count += 1
        log.save()
        return total + 1, delivered, failed_count
