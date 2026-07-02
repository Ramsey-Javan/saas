import pytest

from communication.models import Announcement, MessageTemplate


@pytest.mark.django_db
class TestInputSanitization:
    def test_announcement_body_with_script_tag_is_stored_as_text(self, admin_client, classroom):
        tenant = classroom.tenant
        announcement = Announcement.objects.create(
            tenant=tenant,
            recipient_class=classroom,
            title='Test',
            body='<script>alert(1)</script> Hello',
            recipient_type='class',
            channels=['sms'],
            status='draft',
        )

        assert announcement.body == 'alert(1) Hello'

    def test_message_template_body_strips_tags_on_save(self, tenant):
        template = MessageTemplate.objects.create(
            tenant=tenant,
            name='Test',
            category='general',
            channel='sms',
            body='<b>Hello</b> {{name}}',
        )

        assert template.body == 'Hello {{name}}'
