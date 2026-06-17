"""Curriculum models: subjects, strands, sub-strands, learning outcomes, assignments."""
from django.conf import settings
from django.db import models

from .base import TenantModel


TERM_CHOICES = [
    ('term1', 'Term 1'),
    ('term2', 'Term 2'),
    ('term3', 'Term 3'),
]


class Subject(TenantModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    description = models.TextField(blank=True)
    grade_levels = models.JSONField(default=list)
    is_preloaded = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ['tenant', 'code']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Strand(TenantModel):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='strands')
    name = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ['subject', 'name']

    def __str__(self):
        return f"{self.subject.name} - {self.name}"


class SubStrand(TenantModel):
    strand = models.ForeignKey(Strand, on_delete=models.CASCADE, related_name='sub_strands')
    name = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ['strand', 'name']

    def __str__(self):
        return f"{self.strand.name} - {self.name}"


class LearningOutcome(TenantModel):
    sub_strand = models.ForeignKey(SubStrand, on_delete=models.CASCADE, related_name='outcomes')
    description = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.description[:80]


class ClassSubjectAssignment(TenantModel):
    classroom = models.ForeignKey(
        'students.Classroom',
        on_delete=models.CASCADE,
        related_name='subject_assignments',
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='teaching_assignments',
    )
    academic_year = models.PositiveIntegerField()
    term = models.CharField(max_length=10, choices=TERM_CHOICES)

    class Meta:
        unique_together = ['tenant', 'classroom', 'subject', 'academic_year', 'term']

    def __str__(self):
        return f"{self.classroom} - {self.subject} - {self.academic_year} {self.term}"
