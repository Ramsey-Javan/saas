"""National exam models: sessions, candidates, results."""
from django.conf import settings
from django.db import models

from .base import TenantModel
from .curriculum import TERM_CHOICES


class NationalExamSession(TenantModel):
    class ExamName(models.TextChoices):
        KNAT = 'KNAT', 'Grade 3 National Assessment (KNAT)'
        KPAT = 'KPAT', 'Grade 6 Performance Assessment (KPAT)'
        KJSAT = 'KJSAT', 'Grade 9 Junior School Assessment (KJSAT)'

    name = models.CharField(max_length=10, choices=ExamName.choices)
    academic_year = models.PositiveIntegerField()
    classroom = models.ForeignKey('students.Classroom', on_delete=models.CASCADE, related_name='national_exam_sessions')
    centre_number = models.CharField(max_length=20, blank=True)
    centre_name = models.CharField(max_length=200, blank=True)
    exam_date = models.DateField(null=True, blank=True)
    is_results_entered = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='national_exam_sessions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['tenant', 'name', 'classroom', 'academic_year']

    def __str__(self):
        return f"{self.get_name_display()} - {self.classroom} - {self.academic_year}"


class NationalExamCandidate(TenantModel):
    session = models.ForeignKey(NationalExamSession, on_delete=models.CASCADE, related_name='candidates')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='national_exam_candidates')
    index_number = models.CharField(max_length=20, blank=True)
    is_registered = models.BooleanField(default=False)
    registration_confirmed = models.BooleanField(default=False)
    special_needs = models.TextField(blank=True)

    class Meta:
        unique_together = ['tenant', 'session', 'student']

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.index_number or 'No index'}"


class NationalExamResult(TenantModel):
    candidate = models.ForeignKey(NationalExamCandidate, on_delete=models.CASCADE, related_name='results')
    subject = models.ForeignKey('academics.Subject', on_delete=models.PROTECT, related_name='national_results')
    marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    total_marks = models.PositiveIntegerField(default=100)
    grade = models.CharField(
        max_length=2,
        choices=[
            ('EE', 'Exceeding Expectation'),
            ('ME', 'Meeting Expectation'),
            ('AE', 'Approaching Expectation'),
            ('BE', 'Below Expectation'),
        ],
        blank=True,
    )
    remarks = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ['tenant', 'candidate', 'subject']

    def save(self, *args, **kwargs):
        if self.marks is not None and not self.grade:
            from .grades import ExamConfig
            config = ExamConfig.get_for_tenant(self.candidate.session.tenant)
            self.grade = config.compute_level(self.marks, self.total_marks)
        super().save(*args, **kwargs)
