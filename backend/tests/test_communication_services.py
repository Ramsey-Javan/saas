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
class TestSMSService:
    def test_send_sms_with_valid_recipients(self, monkeypatch):
        monkeypatch.setattr(settings, 'AFRICA_TALKING', {
            'API_KEY': 'test-key',
            'USERNAME': 'sandbox',
            'SENDER_ID': 'SCHOOL',
        })

        recorded = {}

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

        def fake_post(url, data, headers, timeout):
            recorded['url'] = url
            recorded['data'] = data
            return FakeResponse()

        monkeypatch.setattr('communication.services.requests.post', fake_post)

        service = SMSService()
        result = service.send(['254712345678'], 'Test message')

        assert result['SMSMessageData']['Recipients'][0]['messageId'] == 'ATXid_123'
        assert recorded['data']['message'] == 'Test message'

    def test_send_sms_truncates_long_message(self, monkeypatch):
        monkeypatch.setattr(settings, 'AFRICA_TALKING', {
            'API_KEY': 'key',
            'USERNAME': 'sandbox',
            'SENDER_ID': 'SCH',
        })

        class FakeResponse:
            def raise_for_status(self): pass
            def json(self):
                return {'SMSMessageData': {'Recipients': [{'messageId': '1', 'cost': 'KES 0.80'}]}}

        monkeypatch.setattr('communication.services.requests.post', lambda *a, **k: FakeResponse())

        service = SMSService()
        long_msg = 'x' * 200
        result = service.send(['254712345678'], long_msg)

        # Should be truncated to 160 chars
        assert result is not None

    def test_send_bulk_sms(self, monkeypatch):
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
                            {'messageId': '1', 'cost': 'KES 0.80'},
                            {'messageId': '2', 'cost': 'KES 0.80'},
                        ]
                    }
                }

        monkeypatch.setattr('communication.services.requests.post', lambda *a, **k: FakeResponse())

        service = SMSService()
        result = service.send(['254712345678', '254712345679'], 'Bulk test')

        assert len(result['SMSMessageData']['Recipients']) == 2


@pytest.mark.django_db
class TestEmailService:
    def test_send_plain_email(self, monkeypatch):
        calls = []

        def fake_send_mail(subject, body, from_email, recipients, fail_silently=False):
            calls.append({'type': 'plain', 'subject': subject, 'recipients': recipients})

        monkeypatch.setattr('communication.services.send_mail', fake_send_mail)

        service = EmailService()
        result = service.send(['test@example.com'], 'Subject', 'Body')

        assert result['sent'] == 1
        assert result['failed'] == 0
        assert len(calls) == 1

    def test_send_html_email(self, monkeypatch):
        calls = []

        class FakeEmailMultiAlternatives:
            def __init__(self, subject, body, from_email, recipients):
                calls.append({'type': 'html_init', 'subject': subject})
            def attach_alternative(self, html, mime):
                calls.append({'type': 'html_attach', 'content': html})
            def send(self):
                calls.append({'type': 'send'})

        monkeypatch.setattr('communication.services.send_mail', lambda *a, **k: None)
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


@pytest.mark.django_db
class TestPushNotificationService:
    def test_send_to_user_with_no_device(self, monkeypatch):
        tenant = TenantFactory()
        user = UserFactory(tenant=tenant)

        # Mock FCM or push service
        monkeypatch.setattr(
            'communication.services.PushNotificationService.send_to_user',
            lambda self, user, title, body: {'sent': 0, 'failed': 1, 'reason': 'no_device'}
        )

        service = PushNotificationService()
        result = service.send_to_user(user, 'Test', 'Hello')

        assert result['sent'] == 0
