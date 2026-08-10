from django.conf import settings
from django.db import models

from .base import TenantModel


class ScheduleTemplate(TenantModel):
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'name']

    def __str__(self):
        return self.name


class Period(TenantModel):
    class Day(models.IntegerChoices):
        MONDAY = 1, 'Monday'
        TUESDAY = 2, 'Tuesday'
        WEDNESDAY = 3, 'Wednesday'
        THURSDAY = 4, 'Thursday'
        FRIDAY = 5, 'Friday'
        SATURDAY = 6, 'Saturday'
        SUNDAY = 7, 'Sunday'

    schedule_template = models.ForeignKey(
        ScheduleTemplate,
        on_delete=models.CASCADE,
        related_name='periods',
    )
    day_of_week = models.PositiveSmallIntegerField(choices=Day.choices)
    order = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False)

    class Meta:
        ordering = ['schedule_template', 'day_of_week', 'order']
        unique_together = ['tenant', 'schedule_template', 'day_of_week', 'order']

    def __str__(self):
        return f'{self.schedule_template} {self.get_day_of_week_display()} P{self.order}'


class RoomResource(TenantModel):
    class RoomType(models.TextChoices):
        CLASSROOM = 'classroom', 'Classroom'
        LAB = 'lab', 'Lab'
        HALL = 'hall', 'Hall'
        LIBRARY = 'library', 'Library'
        FIELD = 'field', 'Field'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=120)
    room_type = models.CharField(max_length=20, choices=RoomType.choices)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['room_type', 'name']
        unique_together = ['tenant', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_room_type_display()})'


class SubjectRule(TenantModel):
    class TimePreference(models.TextChoices):
        NONE = 'none', 'No preference'
        PREFER_MORNING = 'prefer_morning', 'Prefer morning'
        STRONG_MORNING = 'strong_morning', 'Strongly prefer morning'
        PREFER_AFTERNOON = 'prefer_afternoon', 'Prefer afternoon'

    subject = models.ForeignKey('academics.Subject', on_delete=models.CASCADE, related_name='timetable_rules')
    grade_band = models.CharField(
        max_length=50,
        help_text='Matches students.Classroom.grade_level for this tenant.',
    )
    stream = models.CharField(
        max_length=10,
        blank=True,
        default='',
        help_text=(
            'Optional. Matches students.Classroom.stream exactly (e.g. "West"). '
            'Leave blank to apply this rule to every stream in the grade.'
        ),
    )
    periods_per_week = models.PositiveSmallIntegerField(default=0)
    requires_double = models.BooleanField(default=False)
    requires_room_type = models.CharField(
        max_length=20,
        choices=RoomResource.RoomType.choices,
        null=True,
        blank=True,
    )
    excluded_periods = models.ManyToManyField(Period, blank=True, related_name='excluded_by_rules')
    is_hard_excluded = models.BooleanField(default=True)
    time_preference = models.CharField(
        max_length=20,
        choices=TimePreference.choices,
        default=TimePreference.NONE,
        help_text=(
            'Soft scheduling preference for time of day. Never blocks generation — '
            'the solver will still use an off-preference slot rather than fail to schedule.'
        ),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['grade_band', 'stream', 'subject__name']
        unique_together = ['tenant', 'subject', 'grade_band', 'stream']

    def __str__(self):
        band = f'{self.grade_band} {self.stream}'.strip()
        return f'{band} - {self.subject}'


class TeacherAvailability(TenantModel):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='timetable_availability',
        limit_choices_to={'role': 'teacher'},
    )
    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name='teacher_availability')
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['teacher__last_name', 'period__day_of_week', 'period__order']
        unique_together = ['tenant', 'teacher', 'period']

    def __str__(self):
        status = 'available' if self.is_available else 'blocked'
        return f'{self.teacher} {self.period}: {status}'


class TeacherWorkloadLimit(TenantModel):
    teacher = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='timetable_workload_limit',
        limit_choices_to={'role': 'teacher'},
    )
    max_periods_per_day = models.PositiveSmallIntegerField(null=True, blank=True)
    max_periods_per_week = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['teacher__last_name']

    def __str__(self):
        return f'{self.teacher} workload limits'


class TeacherSubjectAssignment(TenantModel):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='timetable_subject_assignments',
        limit_choices_to={'role': 'teacher'},
    )
    subject = models.ForeignKey('academics.Subject', on_delete=models.CASCADE, related_name='timetable_assignments')
    classroom = models.ForeignKey('students.Classroom', on_delete=models.CASCADE, related_name='timetable_assignments')

    class Meta:
        ordering = ['classroom__name', 'subject__name']
        unique_together = ['tenant', 'teacher', 'subject', 'classroom']

    def __str__(self):
        return f'{self.teacher} - {self.subject} - {self.classroom}'