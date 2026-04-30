from django.contrib import admin
from .models import Subject, Assessment, ReportCard


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'grade_level', 'is_active']
    list_filter = ['grade_level', 'is_active']
    search_fields = ['name', 'code']


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'subject', 'assessment_type', 'competency',
        'marks', 'term', 'academic_year', 'assessment_date',
    ]
    list_filter = ['competency', 'assessment_type', 'term', 'academic_year']
    search_fields = [
        'student__first_name', 'student__last_name', 'student__admission_number',
        'subject__name',
    ]
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['student', 'subject']


@admin.register(ReportCard)
class ReportCardAdmin(admin.ModelAdmin):
    list_display = ['student', 'term', 'academic_year', 'status', 'created_at']
    list_filter = ['term', 'academic_year', 'status']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['student']
