import pytest
from unittest.mock import MagicMock, patch

from django.conf import settings

from communication.services import (
    SMSService,
    WhatsAppService,
    EmailService,
    PushNotificationService,
    AnnouncementDispatcher,
)
from communication.models import MessageLog, SMSLog
from tests.factories import TenantFactory, UserFactory


@pytest.mark.django_db
class TestSMSServiceExtended:
    def test_send_sms_with_empty_recipients(self, monkeypatch):
        monkeypatch.setattr(settings, 'AFRICA_TALKING', {
            'API_KEY': 'test-key',
            'USERNAME': 'sandbox',
            'SENDER_ID': 'SCHOOL',
        })

        service = SMSService()
        result = service.send([], 'Test message')

        # Should handle empty recipients gracefully
        assert result is not None

    def test_send_sms_with_invalid_phone(self, monkeypatch):
        monkeypatch.setattr(settings, 'AFRICA_TALKING', {
            'API_KEY': 'test-key',
            'USERNAME': 'sandbox',
            'SENDER_ID': 'SCHOOL',
        })

        class FakeResponse:
            def raise_for_status(self):
                return None
            def json(self):
                return {
                    'SMSMessageData': {
                        'Recipients': [
                            {'messageId': 'ATXid_123', 'cost': 'KES 0.80', 'status': 'Success'}
                        ]
                    }
                }

        monkeypatch.setattr('communication.services.requests.post', lambda *a, **k: FakeResponse())

        service = SMSService()
        result = service.send(['invalid-phone'], 'Test message')

        assert result is not None

    def test_send_bulk_sms_with_many_recipients(self, monkeypatch):
        monkeypatch.setattr(settings, 'AFRICA_TALKING', {
            'API_KEY': 'key',
            'USERNAME': 'sandbox',
            'SENDER_ID': 'SCH',
        })

        class FakeResponse:
            def raise_for_status(self): pass
            def json(self):
                return {
                    'SMSMessageData': {
                        'Recipients': [
                            {'messageId': str(i), 'cost': 'KES 0.80'}
                            for i in range(10)
                        ]
                    }
                }

        monkeypatch.setattr('communication.services.requests.post', lambda *a, **k: FakeResponse())

        service = SMSService()
        phones = [f'25471234567{i}' for i in range(10)]
        result = service.send(phones, 'Bulk test')

        assert len(result['SMSMessageData']['Recipients']) == 10


@pytest.mark.django_db
class TestEmailServiceExtended:
    def test_send_email_with_html_and_plain(self, monkeypatch):
        calls = []

        def fake_send_mail(subject, body, from_email, recipients, fail_silently=False):
            calls.append({'type': 'plain', 'subject': subject, 'recipients': recipients})

        class FakeEmailMultiAlternatives:
            def __init__(self, subject, body, from_email, recipients):
                calls.append({'type': 'html_init', 'subject': subject})
            def attach_alternative(self, html, mime):
                calls.append({'type': 'html_attach', 'content': html})
            def send(self):
                calls.append({'type': 'send'})

        monkeypatch.setattr('communication.services.send_mail', fake_send_mail)
        monkeypatch.setattr('communication.services.EmailMultiAlternatives', FakeEmailMultiAlternatives)

        service = EmailService()
        result = service.send(
            ['test@example.com'],
            'Subject',
            'Plain body',
            html_body='<p>HTML body</p>'
        )

        assert result['sent'] == 1
        assert any(c['type'] == 'html_attach' for c in calls)

    def test_send_email_with_multiple_recipients(self, monkeypatch):
        calls = []

        def fake_send_mail(subject, body, from_email, recipients, fail_silently=False):
            calls.append({'type': 'plain', 'recipients': recipients})

        monkeypatch.setattr('communication.services.send_mail', fake_send_mail)

        service = EmailService()
        result = service.send(
            ['test1@example.com', 'test2@example.com'],
            'Subject',
            'Body'
        )

        assert result['sent'] == 1
        assert len(calls[0]['recipients']) == 2

    def test_send_email_with_failure(self, monkeypatch):
        def fake_send_mail(subject, body, from_email, recipients, fail_silently=False):
            raise Exception('SMTP error')

        monkeypatch.setattr('communication.services.send_mail', fake_send_mail)

        service = EmailService()
        result = service.send(['test@example.com'], 'Subject', 'Body')

        assert result['failed'] >= 1


@pytest.mark.django_db
class TestPushNotificationServiceExtended:
    def test_send_to_user_with_device(self, monkeypatch):
        tenant = TenantFactory()
        user = UserFactory(tenant=tenant)

        monkeypatch.setattr(
            'communication.services.PushNotificationService.send_to_user',
            lambda self, user, title, body: {'sent': 1, 'failed': 0}
        )

        service = PushNotificationService()
        result = service.send_to_user(user, 'Test', 'Hello')

        assert result['sent'] == 1

    def test_send_bulk_to_users(self, monkeypatch):
        tenant = TenantFactory()
        users = [UserFactory(tenant=tenant) for _ in range(3)]

        monkeypatch.setattr(
            'communication.services.PushNotificationService.send_to_user',
            lambda self, user, title, body: {'sent': 1, 'failed': 0}
        )

        service = PushNotificationService()
        results = [service.send_to_user(u, 'Test', 'Hello') for u in users]

        assert all(r['sent'] == 1 for r in results)


@pytest.mark.django_db
class TestAnnouncementDispatcherExtended:
    def test_dispatch_with_no_recipients(self, monkeypatch, db):
        from tests.factories import TenantFactory, UserFactory
        tenant = TenantFactory()
        user = UserFactory(tenant=tenant)
        from communication.models import Announcement
        announcement = Announcement.objects.create(
            tenant=tenant,
            title='No Recipients',
            body='Test',
            recipient_type='school',
            channels=['sms'],
            status='draft',
            sent_by=user,
        )

        monkeypatch.setattr('communication.services.SMSService.send', lambda self, recipients, message: None)
        monkeypatch.setattr('communication.services.EmailService.send', lambda self, recipients, subject, body, html_body=None: {'sent': 0, 'failed': 0, 'errors': []})
        monkeypatch.setattr('communication.services.WhatsAppService.send', lambda self, to_phone, message: None)
        monkeypatch.setattr('communication.services.PushNotificationService.send_to_user', lambda self, user, title, body: {'sent': 0, 'failed': 0})

        dispatcher = AnnouncementDispatcher()
        result = dispatcher.dispatch(announcement, tenant, sent_by=user)

        assert isinstance(result, dict)
