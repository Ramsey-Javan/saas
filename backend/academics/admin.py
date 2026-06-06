from django.contrib import admin

from .models import (
    AttendanceRecord,
    AttendanceSession,
    CBCGrade,
    ClassSubjectAssignment,
    ClassTimetable,
    CoCurricularActivity,
    ExamCBCSync,
    ExamConfig,
    ExamResult,
    ExamSetup,
    ExamSubject,
    LearningOutcome,
    NationalExamCandidate,
    NationalExamResult,
    NationalExamSession,
    ReportCard,
    Strand,
    StudentCoCurricular,
    Subject,
    SubStrand,
)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'tenant', 'is_preloaded', 'is_active', 'order')
    list_filter = ('tenant', 'is_preloaded', 'is_active')
    search_fields = ('name', 'code', 'description')


@admin.register(Strand)
class StrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'tenant', 'order')
    list_filter = ('tenant', 'subject')
    search_fields = ('name', 'subject__name')


@admin.register(SubStrand)
class SubStrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'strand', 'tenant', 'order')
    list_filter = ('tenant', 'strand__subject')
    search_fields = ('name', 'strand__name', 'strand__subject__name')


@admin.register(LearningOutcome)
class LearningOutcomeAdmin(admin.ModelAdmin):
    list_display = ('sub_strand', 'tenant', 'order', 'description')
    list_filter = ('tenant', 'sub_strand__strand__subject')
    search_fields = ('description', 'sub_strand__name', 'sub_strand__strand__name')


@admin.register(ClassSubjectAssignment)
class ClassSubjectAssignmentAdmin(admin.ModelAdmin):
    list_display = ('classroom', 'subject', 'teacher', 'academic_year', 'term', 'tenant')
    list_filter = ('tenant', 'academic_year', 'term', 'subject')
    search_fields = ('classroom__name', 'subject__name', 'teacher__email')


@admin.register(CBCGrade)
class CBCGradeAdmin(admin.ModelAdmin):
    list_display = ('student', 'learning_outcome', 'term', 'academic_year', 'level', 'assessed_by')
    list_filter = ('tenant', 'term', 'academic_year', 'level')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number', 'remarks')


@admin.register(ExamConfig)
class ExamConfigAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'be_max', 'ae_min', 'me_min', 'ee_min', 'updated_by', 'updated_at')
    list_filter = ('tenant',)


@admin.register(ExamSetup)
class ExamSetupAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam_type', 'classroom', 'term', 'academic_year', 'is_active', 'tenant')
    list_filter = ('tenant', 'exam_type', 'term', 'academic_year', 'is_active')
    search_fields = ('name', 'classroom__name')


@admin.register(ExamSubject)
class ExamSubjectAdmin(admin.ModelAdmin):
    list_display = ('exam', 'subject', 'total_marks', 'teacher', 'tenant')
    list_filter = ('tenant', 'subject')
    search_fields = ('exam__name', 'subject__name', 'teacher__email')


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam_subject', 'marks', 'percentage', 'cbc_level', 'is_overridden', 'tenant')
    list_filter = ('tenant', 'cbc_level', 'is_overridden')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number')


@admin.register(ExamCBCSync)
class ExamCBCSyncAdmin(admin.ModelAdmin):
    list_display = ('exam', 'synced_by', 'synced_at', 'records_synced', 'records_skipped', 'tenant')
    list_filter = ('tenant', 'synced_at')


@admin.register(NationalExamSession)
class NationalExamSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'classroom', 'academic_year', 'centre_number', 'is_results_entered', 'tenant')
    list_filter = ('tenant', 'name', 'academic_year', 'is_results_entered')
    search_fields = ('centre_number', 'centre_name', 'classroom__name')


@admin.register(NationalExamCandidate)
class NationalExamCandidateAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'index_number', 'is_registered', 'registration_confirmed', 'tenant')
    list_filter = ('tenant', 'is_registered', 'registration_confirmed')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number', 'index_number')


@admin.register(NationalExamResult)
class NationalExamResultAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'subject', 'marks', 'total_marks', 'grade', 'tenant')
    list_filter = ('tenant', 'grade', 'subject')
    search_fields = ('candidate__student__first_name', 'candidate__student__last_name', 'candidate__index_number')


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('classroom', 'date', 'session_type', 'subject', 'teacher', 'is_locked')
    list_filter = ('tenant', 'session_type', 'date', 'term', 'academic_year', 'is_locked')
    search_fields = ('classroom__name', 'subject__name', 'teacher__email', 'notes')


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'status', 'tenant')
    list_filter = ('tenant', 'status', 'session__date', 'session__session_type')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number', 'remarks')


@admin.register(ClassTimetable)
class ClassTimetableAdmin(admin.ModelAdmin):
    list_display = ('classroom', 'term', 'academic_year', 'uploaded_by', 'uploaded_at', 'tenant')
    list_filter = ('tenant', 'term', 'academic_year', 'uploaded_at')
    search_fields = ('classroom__name', 'uploaded_by__email', 'notes')


@admin.register(CoCurricularActivity)
class CoCurricularActivityAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'tenant', 'is_active')
    list_filter = ('tenant', 'category', 'is_active')
    search_fields = ('name',)


@admin.register(StudentCoCurricular)
class StudentCoCurricularAdmin(admin.ModelAdmin):
    list_display = ('student', 'activity', 'term', 'academic_year', 'rating', 'tenant')
    list_filter = ('tenant', 'term', 'academic_year', 'rating', 'activity')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number', 'activity__name')


@admin.register(ReportCard)
class ReportCardAdmin(admin.ModelAdmin):
    list_display = ('student', 'classroom', 'term', 'academic_year', 'report_type', 'status', 'generated_at')
    list_filter = ('tenant', 'term', 'academic_year', 'report_type', 'status')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number')
