from django.db import models
from django.conf import settings
from tenants.models import Tenant


class TenantModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class MessageTemplate(TenantModel):
    class Category(models.TextChoices):
        FEE = 'fee', 'Fee Related'
        ATTENDANCE = 'attendance', 'Attendance'
        ACADEMIC = 'academic', 'Academic'
        GENERAL = 'general', 'General'
        EXAM = 'exam', 'Examination'

    class Channel(models.TextChoices):
        SMS = 'sms', 'SMS'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        EMAIL = 'email', 'Email'
        ALL = 'all', 'All Channels'

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=Category.choices)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.ALL)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['tenant', 'name']
        ordering = ['category', 'name']

    def __str__(self):
        return self.name

    def render(self, context: dict) -> str:
        body = self.body
        for key, value in context.items():
            body = body.replace(f'{{{{{key}}}}}', str(value))
        return body

    def render_subject(self, context: dict) -> str:
        subject = self.subject
        for key, value in context.items():
            subject = subject.replace(f'{{{{{key}}}}}', str(value))
        return subject


class Announcement(TenantModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SCHEDULED = 'scheduled', 'Scheduled'
        SENDING = 'sending', 'Sending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    class RecipientType(models.TextChoices):
        CLASS = 'class', 'Specific Class'
        GRADE = 'grade', 'Grade Level'
        SCHOOL = 'school', 'Entire School'
        INDIVIDUAL = 'individual', 'Individual'
        TEACHERS = 'teachers', 'All Teachers'
        STAFF = 'staff', 'All Staff'

    title = models.CharField(max_length=200)
    body = models.TextField()
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='announcements',
    )
    template_vars = models.JSONField(default=dict)
    channels = models.JSONField(default=list)
    recipient_type = models.CharField(max_length=20, choices=RecipientType.choices)
    recipient_class = models.ForeignKey(
        'students.Classroom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='announcements',
    )
    recipient_grade = models.CharField(max_length=20, blank=True)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='targeted_announcements',
    )
    send_immediately = models.BooleanField(default=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.JSONField(default=dict)
    next_run_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_announcements',
    )
    total_recipients = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class MessageLog(TenantModel):
    class Channel(models.TextChoices):
        SMS = 'sms', 'SMS'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        EMAIL = 'email', 'Email'
        INAPP = 'inapp', 'In-App'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        DELIVERED = 'delivered', 'Delivered'
        READ = 'read', 'Read'
        FAILED = 'failed', 'Failed'

    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='logs',
    )
    channel = models.CharField(max_length=10, choices=Channel.choices)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_messages',
    )
    recipient_phone = models.CharField(max_length=20, blank=True)
    recipient_email = models.CharField(max_length=200, blank=True)
    recipient_name = models.CharField(max_length=200, blank=True)
    message_body = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider_message_id = models.CharField(max_length=200, blank=True)
    provider_cost = models.CharField(max_length=50, blank=True)
    failure_reason = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f'{self.channel} to {self.recipient_name or self.recipient_phone or self.recipient_email}'


class InAppNotification(TenantModel):
    class NotificationType(models.TextChoices):
        FEE_REMINDER = 'fee_reminder', 'Fee Reminder'
        ATTENDANCE = 'attendance', 'Attendance Alert'
        REPORT_CARD = 'report_card', 'Report Card'
        ANNOUNCEMENT = 'announcement', 'Announcement'
        EXAM = 'exam', 'Examination'
        SYSTEM = 'system', 'System'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    body = models.TextField()
    type = models.CharField(max_length=20, choices=NotificationType.choices)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    action_url = models.CharField(max_length=500, blank=True)
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='in_app_notifications',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class PushSubscription(TenantModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()
    user_agent = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['tenant', 'user', 'endpoint']


class SMSLog(models.Model):
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    recipient_phone = models.CharField(max_length=15)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    provider = models.CharField(max_length=50, default='africas_talking')
    reference_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f"SMS to {self.recipient_phone} - {self.status}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('payment_reminder', 'Payment Reminder'),
        ('attendance_alert', 'Attendance Alert'),
        ('grade_update', 'Grade Update'),
        ('event', 'Event'),
        ('general', 'General'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
