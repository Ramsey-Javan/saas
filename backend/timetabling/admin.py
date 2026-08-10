from django.contrib import admin

from .models import (
    Period,
    RoomResource,
    ScheduleTemplate,
    SubjectRule,
    TeacherAvailability,
    TeacherSubjectAssignment,
    TeacherWorkloadLimit,
    TimetableEntry,
    TimetableJob,
)


@admin.register(ScheduleTemplate)
class ScheduleTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'is_active')
    list_filter = ('tenant', 'is_active')
    search_fields = ('name',)


@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ('schedule_template', 'day_of_week', 'order', 'start_time', 'end_time', 'is_break', 'tenant')
    list_filter = ('tenant', 'schedule_template', 'day_of_week', 'is_break')


@admin.register(RoomResource)
class RoomResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_type', 'capacity', 'tenant', 'is_active')
    list_filter = ('tenant', 'room_type', 'is_active')
    search_fields = ('name',)


@admin.register(SubjectRule)
class SubjectRuleAdmin(admin.ModelAdmin):
    list_display = ('subject', 'grade_band', 'periods_per_week', 'requires_double', 'requires_room_type', 'tenant')
    list_filter = ('tenant', 'grade_band', 'requires_double', 'requires_room_type')
    search_fields = ('subject__name', 'grade_band')
    filter_horizontal = ('excluded_periods',)


@admin.register(TeacherAvailability)
class TeacherAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'period', 'is_available', 'tenant')
    list_filter = ('tenant', 'is_available', 'period__day_of_week')
    search_fields = ('teacher__email', 'teacher__first_name', 'teacher__last_name')


@admin.register(TeacherWorkloadLimit)
class TeacherWorkloadLimitAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'max_periods_per_day', 'max_periods_per_week', 'tenant')
    list_filter = ('tenant',)
    search_fields = ('teacher__email', 'teacher__first_name', 'teacher__last_name')


@admin.register(TeacherSubjectAssignment)
class TeacherSubjectAssignmentAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'subject', 'classroom', 'tenant')
    list_filter = ('tenant', 'subject', 'classroom')
    search_fields = ('teacher__email', 'subject__name', 'classroom__name')


class TimetableEntryInline(admin.TabularInline):
    model = TimetableEntry
    extra = 0
    fields = ('classroom', 'subject', 'teacher', 'period', 'room', 'locked')


@admin.register(TimetableJob)
class TimetableJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'term', 'academic_year', 'status', 'current_score', 'solve_time_seconds', 'tenant', 'created_at')
    list_filter = ('tenant', 'status', 'term', 'academic_year')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [TimetableEntryInline]


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ('job', 'classroom', 'subject', 'teacher', 'period', 'room', 'locked', 'tenant')
    list_filter = ('tenant', 'job', 'locked', 'period__day_of_week')
    search_fields = ('classroom__name', 'subject__name', 'teacher__email')
