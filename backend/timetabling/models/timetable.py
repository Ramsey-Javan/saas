from django.conf import settings
from django.db import models

from academics.models import TERM_CHOICES
from .base import TenantModel


class TimetableJob(TenantModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        DONE = 'done', 'Done'
        FAILED = 'failed', 'Failed'

    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    academic_year = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_timetable_jobs',
    )
    current_score = models.FloatField(null=True, blank=True)
    best_bound = models.FloatField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    solve_time_seconds = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Timetable {self.term} {self.academic_year} ({self.status})'


class TimetableEntry(TenantModel):
    job = models.ForeignKey(TimetableJob, on_delete=models.CASCADE, related_name='entries')
    classroom = models.ForeignKey('students.Classroom', on_delete=models.CASCADE, related_name='generated_timetable_entries')
    subject = models.ForeignKey('academics.Subject', on_delete=models.CASCADE, related_name='generated_timetable_entries')
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='generated_timetable_entries',
    )
    period = models.ForeignKey('timetabling.Period', on_delete=models.CASCADE, related_name='generated_entries')
    room = models.ForeignKey(
        'timetabling.RoomResource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_entries',
    )
    locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['period__day_of_week', 'period__order', 'classroom__name']
        unique_together = ['job', 'classroom', 'period']

    def __str__(self):
        return f'{self.classroom} {self.period}: {self.subject}'

