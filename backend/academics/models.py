from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from decimal import Decimal

from tenants.models import Tenant


class TenantModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    class Meta:
        abstract = True


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
        LearningOutcome,
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
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='exam_subjects')
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
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='national_results')
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
            config = ExamConfig.get_for_tenant(self.candidate.session.tenant)
            self.grade = config.compute_level(self.marks, self.total_marks)
        super().save(*args, **kwargs)


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
        Subject,
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
