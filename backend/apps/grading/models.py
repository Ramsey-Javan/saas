from django.db import models
from django.conf import settings
from apps.students.models import Student, GRADE_CHOICES


COMPETENCY_CHOICES = [
    ('EE', 'Exceeding Expectation'),
    ('ME', 'Meeting Expectation'),
    ('AE', 'Approaching Expectation'),
    ('BE', 'Below Expectation'),
]

TERM_CHOICES = [
    ('term1', 'Term 1'),
    ('term2', 'Term 2'),
    ('term3', 'Term 3'),
]

ASSESSMENT_TYPE_CHOICES = [
    ('formative', 'Formative Assessment'),
    ('summative', 'Summative Assessment'),
    ('end_of_term', 'End of Term'),
    ('mid_term', 'Mid-Term'),
    ('project', 'Project'),
    ('portfolio', 'Portfolio'),
]


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    grade_level = models.CharField(max_length=5, choices=GRADE_CHOICES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'
        ordering = ['grade_level', 'name']
        unique_together = ['name', 'grade_level']

    def __str__(self):
        return f'{self.name} ({self.code}) - {self.grade_level}'


class Assessment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='assessments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assessments')
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=9, help_text='e.g. 2024/2025')
    assessment_type = models.CharField(max_length=20, choices=ASSESSMENT_TYPE_CHOICES)
    competency = models.CharField(max_length=2, choices=COMPETENCY_CHOICES)
    marks = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Optional raw marks out of max_marks',
    )
    max_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    teacher_remarks = models.TextField(blank=True)
    assessment_date = models.DateField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_assessments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Assessment'
        verbose_name_plural = 'Assessments'
        ordering = ['-assessment_date', 'student__last_name']

    def __str__(self):
        return (
            f'{self.student} - {self.subject.name} - '
            f'{self.assessment_type} - {self.competency} ({self.term} {self.academic_year})'
        )

    @property
    def competency_display(self):
        return dict(COMPETENCY_CHOICES).get(self.competency, self.competency)


class ReportCard(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='report_cards')
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=9)
    class_teacher_remarks = models.TextField(blank=True)
    principal_remarks = models.TextField(blank=True)
    next_term_opening_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_reports',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Report Card'
        verbose_name_plural = 'Report Cards'
        ordering = ['-academic_year', 'term', 'student__last_name']
        unique_together = ['student', 'term', 'academic_year']

    def __str__(self):
        return f'Report Card: {self.student} - {self.term} {self.academic_year}'
