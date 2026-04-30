from django.db import models
from django.contrib.auth import get_user_model
from tenants.models import Tenant

User = get_user_model()


class Class(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    stream = models.CharField(max_length=10, blank=True)
    class_teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    capacity = models.IntegerField(default=40)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('tenant', 'name', 'stream')

    def __str__(self):
        return f"{self.name} {self.stream}" if self.stream else self.name


class Subject(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    is_optional = models.BooleanField(default=False)

    class Meta:
        unique_together = ('tenant', 'code')

    def __str__(self):
        return self.name


class CBCGrade(models.Model):
    GRADE_CHOICES = [
        ('E', 'Excellent'),
        ('V', 'Very Good'),
        ('G', 'Good'),
        ('S', 'Satisfactory'),
        ('A', 'Average'),
        ('B', 'Below Average'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='grades')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.IntegerField(choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')])
    year = models.IntegerField()
    marks = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=1, choices=GRADE_CHOICES)
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'subject', 'term', 'year')

    def __str__(self):
        return f"{self.student} - {self.subject} - Term {self.term}"


class Attendance(models.Model):
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField()
    status = models.CharField(
        max_length=10,
        choices=[('present', 'Present'), ('absent', 'Absent'), ('late', 'Late')]
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.student} - {self.date}"
