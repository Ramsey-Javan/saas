from django.contrib import admin
from .models import SMSLog, Notification


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_phone', 'status', 'provider', 'sent_at', 'created_at')
    list_filter = ('status', 'provider', 'created_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'notification_type', 'user', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
