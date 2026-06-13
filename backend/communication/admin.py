from django.contrib import admin

from .models import (
    Announcement,
    InAppNotification,
    MessageLog,
    MessageTemplate,
    Notification,
    PushSubscription,
    SMSLog,
)


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'channel', 'is_active', 'created_by', 'created_at')
    list_filter = ('category', 'channel', 'is_active', 'created_at')
    search_fields = ('name', 'body')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient_type', 'status', 'sent_by', 'sent_at', 'created_at')
    list_filter = ('status', 'recipient_type', 'is_recurring', 'created_at')
    search_fields = ('title', 'body')


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ('channel', 'recipient_name', 'status', 'sent_at')
    list_filter = ('channel', 'status', 'sent_at')
    search_fields = ('recipient_name', 'recipient_phone', 'recipient_email', 'message_body')


@admin.register(InAppNotification)
class InAppNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'user', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('title', 'body')


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_active', 'subscribed_at')
    list_filter = ('is_active', 'subscribed_at')


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_phone', 'status', 'provider', 'sent_at', 'created_at')
    list_filter = ('status', 'provider', 'created_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'notification_type', 'user', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
