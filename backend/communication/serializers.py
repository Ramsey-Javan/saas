from rest_framework import serializers

from .models import (
    Announcement,
    InAppNotification,
    MessageLog,
    MessageTemplate,
    Notification,
    PushSubscription,
    SMSLog,
)

# Kept in sync with communication.views.TEACHER_ALLOWED_CHANNELS.
TEACHER_ALLOWED_CHANNELS = {'inapp', 'whatsapp'}


class MessageTemplateSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'name', 'category', 'channel', 'subject', 'body', 'is_active',
            'created_by', 'created_by_name', 'created_at',
        ]
        read_only_fields = ['created_by', 'created_at']

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None


class TemplatePreviewSerializer(serializers.Serializer):
    template_vars = serializers.DictField(required=False)


class AnnouncementSerializer(serializers.ModelSerializer):
    sent_by_name = serializers.SerializerMethodField()
    recipient_class_name = serializers.SerializerMethodField()
    delivery_rate = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'body', 'template', 'template_vars', 'channels',
            'recipient_type', 'recipient_class', 'recipient_class_name',
            'recipient_grade', 'recipient_user', 'send_immediately',
            'scheduled_at', 'is_recurring', 'recurrence_rule', 'next_run_at',
            'status', 'sent_at', 'sent_by', 'sent_by_name', 'total_recipients',
            'delivered_count', 'failed_count', 'delivery_rate', 'created_at',
        ]
        read_only_fields = [
            'status', 'sent_at', 'sent_by', 'total_recipients', 'delivered_count',
            'failed_count', 'next_run_at', 'created_at',
        ]

    def get_sent_by_name(self, obj):
        return obj.sent_by.get_full_name() if obj.sent_by else None

    def get_recipient_class_name(self, obj):
        return str(obj.recipient_class) if obj.recipient_class else None

    def get_delivery_rate(self, obj):
        if not obj.total_recipients:
            return 0
        return round(obj.delivered_count / obj.total_recipients * 100, 1)

    def validate_channels(self, value):
        allowed = {'sms', 'whatsapp', 'email', 'inapp'}
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError('Choose at least one channel.')
        invalid = sorted(set(value) - allowed)
        if invalid:
            raise serializers.ValidationError(f'Unsupported channels: {", ".join(invalid)}.')

        # Role-aware restriction, mirrored from the view-level check in
        # AnnouncementViewSet.perform_create. Having it here too means this
        # validation can't be bypassed if this serializer is ever reused
        # from a different view/endpoint that forgets the view-level check.
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and getattr(user, 'role', None) == 'teacher':
            disallowed = sorted(set(value) - TEACHER_ALLOWED_CHANNELS)
            if disallowed:
                raise serializers.ValidationError(
                    f'Teachers can only send via {", ".join(sorted(TEACHER_ALLOWED_CHANNELS))}. '
                    f'Not allowed: {", ".join(disallowed)}.'
                )
        return value


class MessageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageLog
        fields = [
            'id', 'announcement', 'channel', 'recipient_name', 'recipient_phone',
            'recipient_email', 'message_body', 'status', 'provider_message_id',
            'provider_cost', 'failure_reason', 'sent_at', 'delivered_at', 'read_at',
        ]


class InAppNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InAppNotification
        fields = ['id', 'title', 'body', 'type', 'is_read', 'read_at', 'action_url', 'created_at']


class PushSubscriptionSerializer(serializers.Serializer):
    endpoint = serializers.CharField()
    p256dh = serializers.CharField()
    auth = serializers.CharField()
    user_agent = serializers.CharField(required=False, default='', allow_blank=True)


class SMSLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SMSLog
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'