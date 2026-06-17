"""School life models: attendance, timetables, co-curricular, report cards."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .base import TenantModel


class AttendanceSession(TenantModel):
    class SessionType(models.TextChoices):
        DAILY = 'daily', 'Daily'
        MORNING = 'morning', 'Morning Session'
        AFTERNOON = 'afternoon', 'Afternoon Session'
        LESSON = 'lesson', 'Single Lesson'

    classroom = models.ForeignKey(
        'students.Classroom',
        on_delete=models.CASCADE,
        related_name='attendance_sessions',
    )
    subject = models.ForeignKey(
        'academics.Subject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_sessions',
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='attendance_sessions',
    )
    date = models.DateField()
    session_type = models.CharField(
        max_length=15,
        choices=SessionType.choices,
        default=SessionType.DAILY,
    )
    term = models.CharField(max_length=10)
    academic_year = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    is_locked = models.BooleanField(default=False)

    class Meta:
        unique_together = ['tenant', 'classroom', 'date', 'session_type', 'subject']

    def __str__(self):
        return f"{self.classroom} - {self.date} - {self.session_type}"


class AttendanceRecord(TenantModel):
    class Status(models.TextChoices):
        PRESENT = 'P', 'Present'
        ABSENT = 'A', 'Absent'
        LATE = 'L', 'Late'
        EXCUSED = 'E', 'Excused Absence'

    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name='records',
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    status = models.CharField(max_length=1, choices=Status.choices, default=Status.PRESENT)
    remarks = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ['tenant', 'session', 'student']

    def __str__(self):
        return f"{self.student} - {self.session} - {self.status}"


class ClassTimetable(TenantModel):
    classroom = models.ForeignKey(
        'students.Classroom',
        on_delete=models.CASCADE,
        related_name='timetables',
    )
    term = models.CharField(max_length=10)
    academic_year = models.PositiveIntegerField()
    file = models.FileField(upload_to='timetables/')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_timetables',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['tenant', 'classroom', 'term', 'academic_year']

    def __str__(self):
        return f"{self.classroom} timetable - {self.term} {self.academic_year}"


class CoCurricularActivity(TenantModel):
    class Category(models.TextChoices):
        SPORTS = 'sports', 'Sports'
        ARTS = 'arts', 'Arts & Culture'
        COMMUNITY = 'community', 'Community Service'
        CLUBS = 'clubs', 'Clubs & Societies'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=Category.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['tenant', 'name']

    def __str__(self):
        return self.name


class StudentCoCurricular(TenantModel):
    class Rating(models.TextChoices):
        EXCELLENT = 'excellent', 'Excellent'
        GOOD = 'good', 'Good'
        SATISFACTORY = 'satisfactory', 'Satisfactory'
        NEEDS_IMPROVEMENT = 'needs_improvement', 'Needs Improvement'

    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='co_curricular',
    )
    activity = models.ForeignKey(
        CoCurricularActivity,
        on_delete=models.PROTECT,
        related_name='student_records',
    )
    term = models.CharField(max_length=10)
    academic_year = models.PositiveIntegerField()
    rating = models.CharField(max_length=20, choices=Rating.choices)
    remarks = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ['tenant', 'student', 'activity', 'term', 'academic_year']

    def __str__(self):
        return f"{self.student} - {self.activity} - {self.rating}"


class ReportCard(TenantModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'

    class ReportType(models.TextChoices):
        TERMLY = 'termly', 'Termly'
        ANNUAL = 'annual', 'Annual Summary'

    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='report_cards',
    )
    classroom = models.ForeignKey(
        'students.Classroom',
        on_delete=models.SET_NULL,
        null=True,
        related_name='report_cards',
    )
    term = models.CharField(max_length=10, blank=True)
    academic_year = models.PositiveIntegerField()
    report_type = models.CharField(
        max_length=10,
        choices=ReportType.choices,
        default=ReportType.TERMLY,
    )
    days_school_open = models.PositiveIntegerField(default=0)
    days_present = models.PositiveIntegerField(default=0)
    days_absent = models.PositiveIntegerField(default=0)
    days_late = models.PositiveIntegerField(default=0)
    conduct_discipline = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
    )
    conduct_respect = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
    )
    conduct_responsibility = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
    )
    conduct_punctuality = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
    )
    conduct_participation = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
    )
    class_teacher_remarks = models.TextField(blank=True)
    principal_remarks = models.TextField(blank=True)
    closing_date = models.DateField(null=True, blank=True)
    next_term_opening_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_report_cards',
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    pdf_file = models.FileField(upload_to='report_cards/', null=True, blank=True)

    class Meta:
        unique_together = ['tenant', 'student', 'term', 'academic_year', 'report_type']

    def __str__(self):
        return f"{self.student} - {self.academic_year} {self.term or self.report_type}"
