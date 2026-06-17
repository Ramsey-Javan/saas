"""School life serializers: attendance, timetables, co-curricular, report cards."""
from rest_framework import serializers

from ..models import (
    AttendanceRecord,
    AttendanceSession,
    ClassTimetable,
    CoCurricularActivity,
    ReportCard,
    StudentCoCurricular,
)


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'session', 'student',
            'student_name', 'admission_number',
            'status', 'remarks',
        ]

    def get_student_name(self, obj):
        return obj.student.get_full_name()

    def get_admission_number(self, obj):
        return obj.student.admission_number


class AttendanceSessionSerializer(serializers.ModelSerializer):
    records = AttendanceRecordSerializer(many=True, read_only=True)
    classroom_name = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    present_count = serializers.SerializerMethodField()
    absent_count = serializers.SerializerMethodField()
    total_students = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'classroom', 'classroom_name',
            'subject', 'subject_name',
            'teacher', 'teacher_name',
            'date', 'session_type', 'term', 'academic_year',
            'notes', 'is_locked',
            'present_count', 'absent_count', 'total_students',
            'records',
        ]
        read_only_fields = ['is_locked']

    def get_classroom_name(self, obj):
        return str(obj.classroom)

    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() if obj.teacher else None

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else None

    def get_present_count(self, obj):
        return obj.records.filter(status='P').count()

    def get_absent_count(self, obj):
        return obj.records.filter(status='A').count()

    def get_total_students(self, obj):
        return obj.records.count()


class AttendanceSessionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for attendance session lists."""

    classroom_name = serializers.SerializerMethodField()
    present_count = serializers.SerializerMethodField()
    absent_count = serializers.SerializerMethodField()
    total_students = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'classroom', 'classroom_name',
            'date', 'session_type', 'term', 'academic_year',
            'is_locked', 'present_count',
            'absent_count', 'total_students',
        ]

    def get_classroom_name(self, obj):
        return str(obj.classroom)

    def get_present_count(self, obj):
        return obj.records.filter(status='P').count()

    def get_absent_count(self, obj):
        return obj.records.filter(status='A').count()

    def get_total_students(self, obj):
        return obj.records.count()


class MarkAttendanceSerializer(serializers.Serializer):
    """Bulk attendance marking payload."""

    records = serializers.ListField(child=serializers.DictField())


class ClassTimetableSerializer(serializers.ModelSerializer):
    classroom_name = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ClassTimetable
        fields = [
            'id', 'classroom', 'classroom_name',
            'term', 'academic_year',
            'file', 'file_url', 'notes',
            'uploaded_by', 'uploaded_by_name',
            'uploaded_at',
        ]
        read_only_fields = ['uploaded_by', 'uploaded_at']

    def get_classroom_name(self, obj):
        return str(obj.classroom)

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name() if obj.uploaded_by else None

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class CoCurricularActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = CoCurricularActivity
        fields = ['id', 'name', 'category', 'is_active']


class StudentCoCurricularSerializer(serializers.ModelSerializer):
    activity_name = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentCoCurricular
        fields = [
            'id', 'student', 'student_name',
            'activity', 'activity_name',
            'term', 'academic_year',
            'rating', 'remarks',
        ]

    def get_activity_name(self, obj):
        return obj.activity.name

    def get_student_name(self, obj):
        return obj.student.get_full_name()


class ReportCardSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()
    classroom_name = serializers.SerializerMethodField()
    generated_by_name = serializers.SerializerMethodField()
    attendance_percentage = serializers.SerializerMethodField()

    class Meta:
        model = ReportCard
        fields = [
            'id', 'student', 'student_name',
            'admission_number', 'classroom', 'classroom_name',
            'term', 'academic_year', 'report_type',
            'days_school_open', 'days_present',
            'days_absent', 'days_late',
            'attendance_percentage',
            'conduct_discipline', 'conduct_respect',
            'conduct_responsibility', 'conduct_punctuality',
            'conduct_participation',
            'class_teacher_remarks', 'principal_remarks',
            'closing_date', 'next_term_opening_date',
            'status', 'generated_by', 'generated_by_name',
            'generated_at', 'published_at', 'pdf_file',
        ]
        read_only_fields = ['generated_by', 'generated_at', 'published_at', 'pdf_file']

    def get_student_name(self, obj):
        return obj.student.get_full_name()

    def get_admission_number(self, obj):
        return obj.student.admission_number

    def get_classroom_name(self, obj):
        return str(obj.classroom) if obj.classroom else None

    def get_generated_by_name(self, obj):
        return obj.generated_by.get_full_name() if obj.generated_by else None

    def get_attendance_percentage(self, obj):
        if not obj.days_school_open:
            return 0
        return round((obj.days_present / obj.days_school_open) * 100, 1)


from students.models import Classroom


class GenerateReportCardSerializer(serializers.Serializer):
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all())
    term = serializers.CharField()
    academic_year = serializers.IntegerField()
    report_type = serializers.ChoiceField(choices=['termly', 'annual'], default='termly')
    closing_date = serializers.DateField(required=False, allow_null=True)
    next_term_opening_date = serializers.DateField(required=False, allow_null=True)
