from django.db import models
from django.conf import settings
from apps.students.models import Student


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
        ('half_day', 'Half Day'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_records',
    )
    remarks = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Attendance Record'
        verbose_name_plural = 'Attendance Records'
        ordering = ['-date', 'student__last_name']
        unique_together = ['student', 'date']

    def __str__(self):
        return f'{self.student} - {self.date} - {self.status}'
