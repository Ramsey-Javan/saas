from django.conf import settings
from django.db import models
from tenants.models import Tenant


class SchoolEvent(models.Model):
    """
    Manually-created calendar events for the admin dashboard's Upcoming
    Events widget (e.g. Parent-Teacher Meeting, Sports Day, school closing
    dates). Distinct from auto-computed deadlines (fee due dates, exam
    start dates, report card windows), which are derived live from
    FeeStructure / ExamSetup / ReportCard and merged in alongside these at
    read time — see dashboard/views.py: upcoming_events.
    """
    class Category(models.TextChoices):
        EVENT = 'event', 'School Event'
        MEETING = 'meeting', 'Meeting'
        HOLIDAY = 'holiday', 'Holiday / Closure'
        DEADLINE = 'deadline', 'Deadline'
        OTHER = 'other', 'Other'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='school_events')
    title = models.CharField(max_length=200)
    date = models.DateField()
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.EVENT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_school_events',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f'{self.title} ({self.date})'