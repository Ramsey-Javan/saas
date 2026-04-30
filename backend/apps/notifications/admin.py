from django.contrib import admin
from .models import SMSLog


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ['recipient_phone', 'status', 'message_id', 'student', 'sent_by', 'sent_at', 'created_at']
    list_filter = ['status']
    search_fields = ['recipient_phone', 'message', 'message_id']
    readonly_fields = ['created_at', 'sent_at', 'provider_response', 'message_id']
    ordering = ['-created_at']
