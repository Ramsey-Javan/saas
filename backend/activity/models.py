import uuid

from django.conf import settings
from django.db import models

from tenants.models import Tenant


class ActivityLog(models.Model):
    """Central audit trail for everything that happens across the school."""

    class ActivityType(models.TextChoices):
        # Students
        STUDENT_ADMITTED = 'student_admitted', 'Student Admitted'
        STUDENT_TRANSFERRED = 'student_transferred', 'Student Transferred'
        STUDENT_GRADUATED = 'student_graduated', 'Student Graduated'
        STUDENT_DROPPED = 'student_dropped', 'Student Dropped'
        STUDENT_PROMOTED = 'student_promoted', 'Student Promoted'

        # Staff
        STAFF_INVITED = 'staff_invited', 'Staff Invited'
        STAFF_JOINED = 'staff_joined', 'Staff Joined'
        STAFF_DEACTIVATED = 'staff_deactivated', 'Staff Deactivated'
        STAFF_REACTIVATED = 'staff_reactivated', 'Staff Reactivated'

        # Finance
        FEE_PAID = 'fee_paid', 'Fee Paid'
        INVOICE_GENERATED = 'invoice_generated', 'Invoice Generated'
        INVOICE_BULK_GENERATED = 'invoice_bulk_generated', 'Bulk Invoices Generated'
        WAIVER_APPROVED = 'waiver_approved', 'Waiver Approved'
        WAIVER_APPLIED = 'waiver_applied', 'Waiver Applied'
        RECEIPT_ISSUED = 'receipt_issued', 'Receipt Issued'

        # Communication
        ANNOUNCEMENT_SENT = 'announcement_sent', 'Announcement Sent'
        ANNOUNCEMENT_SCHEDULED = 'announcement_scheduled', 'Announcement Scheduled'
        MESSAGE_SENT = 'message_sent', 'Message Sent'

        # Academics
        EXAM_CREATED = 'exam_created', 'Exam Created'
        EXAM_RESULTS_PUBLISHED = 'exam_results_published', 'Exam Results Published'
        REPORT_CARD_GENERATED = 'report_card_generated', 'Report Card Generated'
        REPORT_CARD_PUBLISHED = 'report_card_published', 'Report Card Published'
        ATTENDANCE_MARKED = 'attendance_marked', 'Attendance Marked'
        GRADE_ENTERED = 'grade_entered', 'Grade Entered'
        TIMETABLE_UPLOADED = 'timetable_uploaded', 'Timetable Uploaded'

        # System
        LOGIN = 'login', 'User Login'
        LOGOUT = 'logout', 'User Logout'
        SETTINGS_UPDATED = 'settings_updated', 'Settings Updated'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='activity_logs',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities',
    )
    activity_type = models.CharField(
        max_length=50,
        choices=ActivityType.choices,
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    target_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="Django model label, e.g. 'students.Student'",
    )
    target_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Target object UUID or PK",
    )
    target_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Human readable target name",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_system = models.BooleanField(
        default=False,
        help_text="True for automated/system actions",
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', '-created_at']),
            models.Index(fields=['tenant', 'activity_type', '-created_at']),
            models.Index(fields=['tenant', 'actor', '-created_at']),
        ]

    def __str__(self):
        return f"{self.activity_type} - {self.title}"