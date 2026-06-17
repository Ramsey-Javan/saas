"""Grades and exam models: CBC grades, exam configs, exam setups, exam subjects, exam results, CBC sync."""
from decimal import Decimal

from django.conf import settings
from django.db import models

from .base import TenantModel
from .curriculum import TERM_CHOICES


class CBCGrade(TenantModel):
    class Level(models.TextChoices):
        EE = 'EE', 'Exceeding Expectation'
        ME = 'ME', 'Meeting Expectation'
        AE = 'AE', 'Approaching Expectation'
        BE = 'BE', 'Below Expectation'

    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='cbc_grades',
    )
    learning_outcome = models.ForeignKey(
        'academics.LearningOutcome',
        on_delete=models.PROTECT,
        related_name='grades',
    )
    term = models.CharField(max_length=10)
    academic_year = models.PositiveIntegerField()
    level = models.CharField(max_length=2, choices=Level.choices)
    remarks = models.TextField(blank=True)
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='grades_given',
    )
    assessed_on = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ['tenant', 'student', 'learning_outcome', 'term', 'academic_year']

    def __str__(self):
        return f"{self.student} - {self.learning_outcome} - {self.level}"


class ExamConfig(TenantModel):
    be_min = models.PositiveIntegerField(default=0)
    be_max = models.PositiveIntegerField(default=29)
    ae_min = models.PositiveIntegerField(default=30)
    ae_max = models.PositiveIntegerField(default=49)
    me_min = models.PositiveIntegerField(default=50)
    me_max = models.PositiveIntegerField(default=74)
    ee_min = models.PositiveIntegerField(default=75)
    ee_max = models.PositiveIntegerField(default=100)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='exam_config_updates',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['tenant']

    @classmethod
    def get_for_tenant(cls, tenant):
        obj, _ = cls.objects.get_or_create(
            tenant=tenant,
            defaults={
                'be_min': 0, 'be_max': 29,
                'ae_min': 30, 'ae_max': 49,
                'me_min': 50, 'me_max': 74,
                'ee_min': 75, 'ee_max': 100,
            },
        )
        return obj

    def compute_level(self, marks, total_marks):
        if total_marks <= 0:
            return 'BE'
        pct = (Decimal(str(marks)) / Decimal(str(total_marks))) * 100
        if pct >= self.ee_min:
            return 'EE'
        if pct >= self.me_min:
            return 'ME'
        if pct >= self.ae_min:
            return 'AE'
        return 'BE'


class ExamSetup(TenantModel):
    class ExamType(models.TextChoices):
        OPENER = 'opener', 'Opener Exam'
        MIDTERM = 'midterm', 'Mid-Term Exam'
        ENDTERM = 'endterm', 'End Term Exam'
        MOCK = 'mock', 'Mock Exam'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=200)
    exam_type = models.CharField(max_length=10, choices=ExamType.choices)
    classroom = models.ForeignKey('students.Classroom', on_delete=models.CASCADE, related_name='exam_setups')
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    academic_year = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_exams',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-academic_year', '-start_date']
        unique_together = ['tenant', 'name', 'classroom', 'term', 'academic_year']

    def __str__(self):
        return f"{self.name} - {self.classroom}"


class ExamSubject(TenantModel):
    exam = models.ForeignKey(ExamSetup, on_delete=models.CASCADE, related_name='exam_subjects')
    subject = models.ForeignKey('academics.Subject', on_delete=models.PROTECT, related_name='exam_subjects')
    total_marks = models.PositiveIntegerField(default=100)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='exam_subjects_teaching',
    )

    class Meta:
        unique_together = ['exam', 'subject']

    def __str__(self):
        return f"{self.subject.name} - {self.exam.name} (/{self.total_marks})"


class ExamResult(TenantModel):
    exam_subject = models.ForeignKey(ExamSubject, on_delete=models.CASCADE, related_name='results')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='exam_results')
    marks = models.DecimalField(max_digits=6, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    cbc_level = models.CharField(
        max_length=2,
        choices=[
            ('EE', 'Exceeding Expectation'),
            ('ME', 'Meeting Expectation'),
            ('AE', 'Approaching Expectation'),
            ('BE', 'Below Expectation'),
        ],
    )
    is_overridden = models.BooleanField(default=False)
    override_reason = models.CharField(max_length=200, blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='exam_results_entered',
    )
    entered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['tenant', 'exam_subject', 'student']

    def save(self, *args, **kwargs):
        if self.exam_subject.total_marks > 0:
            self.percentage = (Decimal(str(self.marks)) / Decimal(str(self.exam_subject.total_marks))) * 100
        if not self.is_overridden:
            config = ExamConfig.get_for_tenant(self.tenant)
            self.cbc_level = config.compute_level(self.marks, self.exam_subject.total_marks)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.exam_subject.subject.name} - {self.marks}/{self.exam_subject.total_marks} ({self.cbc_level})"


class ExamCBCSync(TenantModel):
    exam = models.ForeignKey(ExamSetup, on_delete=models.CASCADE, related_name='cbc_syncs')
    synced_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cbc_syncs',
    )
    synced_at = models.DateTimeField(auto_now_add=True)
    records_synced = models.PositiveIntegerField(default=0)
    records_skipped = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-synced_at']
