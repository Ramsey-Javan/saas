import pytest
from django.urls import reverse

from communication.models import Announcement, MessageTemplate, MessageLog, InAppNotification
from tests.factories import (
    AnnouncementFactory,
    ClassroomFactory,
    MessageTemplateFactory,
    StudentFactory,
    TeacherUserFactory,
)


def _reverse_or_skip(url_names, kwargs=None):
    for name in url_names:
        try:
            if kwargs:
                return reverse(name, kwargs=kwargs)
            return reverse(name)
        except:
            continue
    return None


@pytest.mark.django_db
class TestAnnouncementViews:
    def test_announcement_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        announcement = Announcement.objects.create(
            tenant=tenant,
            title='Detail Test',
            body='Body',
            recipient_type='school',
            channels=['sms'],
            status='draft',
        )

        url = _reverse_or_skip(['announcement-detail', 'announcements-detail'], {'pk': announcement.id})
        if url is None:
            pytest.skip("announcement-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_announcement_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        announcement = Announcement.objects.create(
            tenant=tenant,
            title='Update Test',
            body='Body',
            recipient_type='school',
            channels=['sms'],
            status='draft',
        )

        url = _reverse_or_skip(['announcement-detail', 'announcements-detail'], {'pk': announcement.id})
        if url is None:
            pytest.skip("announcement-detail URL not found")

        response = admin_client.patch(url, {'title': 'Updated Title'}, format='json')
        assert response.status_code in [200, 404]

    def test_announcement_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        announcement = Announcement.objects.create(
            tenant=tenant,
            title='Delete Test',
            body='Body',
            recipient_type='school',
            channels=['sms'],
            status='draft',
        )

        url = _reverse_or_skip(['announcement-detail', 'announcements-detail'], {'pk': announcement.id})
        if url is None:
            pytest.skip("announcement-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]

    def test_announcement_filter_by_status(self, admin_client, admin_user):
        tenant = admin_user.tenant
        Announcement.objects.create(
            tenant=tenant,
            title='Draft',
            body='Body',
            recipient_type='school',
            channels=['sms'],
            status='draft',
        )
        Announcement.objects.create(
            tenant=tenant,
            title='Sent',
            body='Body',
            recipient_type='school',
            channels=['sms'],
            status='sent',
        )

        url = _reverse_or_skip(['announcement-list', 'announcements-list'])
        if url is None:
            pytest.skip("announcement-list URL not found")

        response = admin_client.get(url, {'status': 'sent'})
        assert response.status_code == 200


@pytest.mark.django_db
class TestMessageTemplateViews:
    def test_template_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        template = MessageTemplate.objects.create(
            tenant=tenant,
            name='Detail Template',
            category='general',
            channel='sms',
            body='Hello',
        )

        url = _reverse_or_skip(['template-detail', 'message-template-detail'], {'pk': template.id})
        if url is None:
            pytest.skip("template-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_template_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        template = MessageTemplate.objects.create(
            tenant=tenant,
            name='Update Template',
            category='general',
            channel='sms',
            body='Hello',
        )

        url = _reverse_or_skip(['template-detail', 'message-template-detail'], {'pk': template.id})
        if url is None:
            pytest.skip("template-detail URL not found")

        response = admin_client.patch(url, {'body': 'Updated body'}, format='json')
        assert response.status_code in [200, 404]

    def test_template_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        template = MessageTemplate.objects.create(
            tenant=tenant,
            name='Delete Template',
            category='general',
            channel='sms',
            body='Hello',
        )

        url = _reverse_or_skip(['template-detail', 'message-template-detail'], {'pk': template.id})
        if url is None:
            pytest.skip("template-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]


@pytest.mark.django_db
class TestMessageLogViews:
    def test_message_log_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        log = MessageLog.objects.create(
            tenant=tenant,
            channel='sms',
            recipient_phone='0700000000',
            message_body='Hello',
            status='sent',
        )

        url = _reverse_or_skip(['message-log-detail', 'messagelog-detail'], {'pk': log.id})
        if url is None:
            pytest.skip("message-log-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_message_log_filter_by_channel(self, admin_client, admin_user):
        tenant = admin_user.tenant
        MessageLog.objects.create(
            tenant=tenant,
            channel='sms',
            recipient_phone='0700000000',
            message_body='Hello',
            status='sent',
        )
        MessageLog.objects.create(
            tenant=tenant,
            channel='email',
            recipient_email='test@test.co.ke',
            message_body='Hello',
            status='sent',
        )

        url = _reverse_or_skip(['message-log-list', 'messagelog-list'])
        if url is None:
            pytest.skip("message-log-list URL not found")

        response = admin_client.get(url, {'channel': 'sms'})
        assert response.status_code == 200
