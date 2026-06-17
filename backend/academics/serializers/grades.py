"""Grades and exam serializers."""
from rest_framework import serializers

from students.models import Classroom

from ..models import (
    CBCGrade,
    ExamCBCSync,
    ExamConfig,
    ExamResult,
    ExamSetup,
    ExamSubject,
    LearningOutcome,
)


class CBCGradeSerializer(serializers.ModelSerializer):
    outcome_description = serializers.SerializerMethodField()
    sub_strand_name = serializers.SerializerMethodField()
    strand_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    assessed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CBCGrade
        fields = [
            'id', 'student', 'learning_outcome',
            'outcome_description', 'sub_strand_name',
            'strand_name', 'subject_name',
            'term', 'academic_year', 'level',
            'remarks', 'assessed_by', 'assessed_by_name',
            'assessed_on',
        ]
        read_only_fields = ['assessed_by', 'assessed_on']

    def get_outcome_description(self, obj):
        return obj.learning_outcome.description

    def get_sub_strand_name(self, obj):
        return obj.learning_outcome.sub_strand.name

    def get_strand_name(self, obj):
        return obj.learning_outcome.sub_strand.strand.name

    def get_subject_name(self, obj):
        return obj.learning_outcome.sub_strand.strand.subject.name

    def get_assessed_by_name(self, obj):
        return obj.assessed_by.get_full_name() if obj.assessed_by else None


class BulkGradeSerializer(serializers.Serializer):
    """Grade multiple students on one learning outcome."""

    learning_outcome = serializers.PrimaryKeyRelatedField(queryset=LearningOutcome.objects.all())
    term = serializers.CharField()
    academic_year = serializers.IntegerField()
    grades = serializers.ListField(child=serializers.DictField())


class GradeImportSerializer(serializers.Serializer):
    """CSV bulk import payload."""

    file = serializers.FileField()
    term = serializers.CharField()
    academic_year = serializers.IntegerField()
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all())


class ExamConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamConfig
        fields = [
            'id', 'be_min', 'be_max',
            'ae_min', 'ae_max',
            'me_min', 'me_max',
            'ee_min', 'ee_max',
            'updated_by', 'updated_at',
        ]
        read_only_fields = ['updated_by', 'updated_at']

    def validate(self, attrs):
        be_max = attrs.get('be_max', getattr(self.instance, 'be_max', 29))
        ae_min = attrs.get('ae_min', getattr(self.instance, 'ae_min', 30))
        ae_max = attrs.get('ae_max', getattr(self.instance, 'ae_max', 49))
        me_min = attrs.get('me_min', getattr(self.instance, 'me_min', 50))
        me_max = attrs.get('me_max', getattr(self.instance, 'me_max', 74))
        ee_min = attrs.get('ee_min', getattr(self.instance, 'ee_min', 75))
        if ae_min != be_max + 1:
            raise serializers.ValidationError('AE min must equal BE max + 1')
        if me_min != ae_max + 1:
            raise serializers.ValidationError('ME min must equal AE max + 1')
        if ee_min != me_max + 1:
            raise serializers.ValidationError('EE min must equal ME max + 1')
        return attrs


class ExamSubjectSerializer(serializers.ModelSerializer):
    subject_name = serializers.SerializerMethodField()
    subject_code = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    results_count = serializers.SerializerMethodField()

    class Meta:
        model = ExamSubject
        fields = [
            'id', 'exam', 'subject', 'subject_name', 'subject_code',
            'total_marks', 'teacher', 'teacher_name', 'results_count',
        ]

    def get_subject_name(self, obj):
        return obj.subject.name

    def get_subject_code(self, obj):
        return obj.subject.code

    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() if obj.teacher else None

    def get_results_count(self, obj):
        return obj.results.count()


class ExamSetupSerializer(serializers.ModelSerializer):
    exam_subjects = ExamSubjectSerializer(many=True, read_only=True)
    classroom_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    total_students = serializers.SerializerMethodField()

    class Meta:
        model = ExamSetup
        fields = [
            'id', 'name', 'exam_type',
            'classroom', 'classroom_name',
            'term', 'academic_year',
            'start_date', 'end_date',
            'instructions', 'is_active',
            'exam_subjects', 'total_students',
            'created_by', 'created_by_name',
            'created_at',
        ]
        read_only_fields = ['created_by', 'created_at']

    def get_classroom_name(self, obj):
        return str(obj.classroom)

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None

    def get_total_students(self, obj):
        from students.models import Student
        return Student.objects.filter(classroom=obj.classroom, is_active=True).count()


class ExamSetupListSerializer(serializers.ModelSerializer):
    classroom_name = serializers.SerializerMethodField()
    subjects_count = serializers.SerializerMethodField()
    total_students = serializers.SerializerMethodField()
    results_count = serializers.SerializerMethodField()
    last_sync_at = serializers.SerializerMethodField()

    class Meta:
        model = ExamSetup
        fields = [
            'id', 'name', 'exam_type',
            'classroom', 'classroom_name',
            'term', 'academic_year',
            'start_date', 'end_date',
            'is_active', 'subjects_count',
            'total_students', 'results_count', 'last_sync_at',
        ]

    def get_classroom_name(self, obj):
        return str(obj.classroom)

    def get_subjects_count(self, obj):
        return obj.exam_subjects.count()

    def get_total_students(self, obj):
        from students.models import Student
        return Student.objects.filter(classroom=obj.classroom, is_active=True).count()

    def get_results_count(self, obj):
        return ExamResult.objects.filter(exam_subject__exam=obj).count()

    def get_last_sync_at(self, obj):
        sync = obj.cbc_syncs.order_by('-synced_at').first()
        return sync.synced_at if sync else None


class ExamResultSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    subject_code = serializers.SerializerMethodField()
    exam_name = serializers.SerializerMethodField()
    exam_type = serializers.SerializerMethodField()
    exam_term = serializers.SerializerMethodField()
    exam_academic_year = serializers.SerializerMethodField()
    total_marks = serializers.SerializerMethodField()
    entered_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ExamResult
        fields = [
            'id', 'exam_subject', 'student',
            'student_name', 'admission_number',
            'subject_name', 'subject_code',
            'exam_name', 'exam_type', 'exam_term', 'exam_academic_year',
            'marks', 'total_marks', 'percentage',
            'cbc_level', 'is_overridden',
            'override_reason', 'entered_by',
            'entered_by_name', 'entered_at',
        ]
        read_only_fields = ['percentage', 'entered_by', 'entered_at']

    def get_student_name(self, obj):
        return obj.student.get_full_name()

    def get_admission_number(self, obj):
        return obj.student.admission_number

    def get_subject_name(self, obj):
        return obj.exam_subject.subject.name

    def get_subject_code(self, obj):
        return obj.exam_subject.subject.code

    def get_exam_name(self, obj):
        return obj.exam_subject.exam.name

    def get_exam_type(self, obj):
        return obj.exam_subject.exam.exam_type

    def get_exam_term(self, obj):
        return obj.exam_subject.exam.term

    def get_exam_academic_year(self, obj):
        return obj.exam_subject.exam.academic_year

    def get_total_marks(self, obj):
        return obj.exam_subject.total_marks

    def get_entered_by_name(self, obj):
        return obj.entered_by.get_full_name() if obj.entered_by else None

    def validate_marks(self, value):
        exam_subject_id = self.initial_data.get('exam_subject') or (self.instance.exam_subject_id if self.instance else None)
        if exam_subject_id:
            try:
                exam_subject = ExamSubject.objects.get(id=exam_subject_id)
                if value > exam_subject.total_marks:
                    raise serializers.ValidationError(f'Marks cannot exceed {exam_subject.total_marks} (total marks for this subject).')
            except ExamSubject.DoesNotExist:
                pass
        if value < 0:
            raise serializers.ValidationError('Marks cannot be negative.')
        return value


class BulkExamResultSerializer(serializers.Serializer):
    exam_subject = serializers.PrimaryKeyRelatedField(queryset=ExamSubject.objects.all())
    results = serializers.ListField(child=serializers.DictField())


class ExamResultImportSerializer(serializers.Serializer):
    file = serializers.FileField()
    exam_setup = serializers.PrimaryKeyRelatedField(queryset=ExamSetup.objects.all())


class ExamCBCSyncSerializer(serializers.ModelSerializer):
    synced_by_name = serializers.SerializerMethodField()
    exam_name = serializers.SerializerMethodField()

    class Meta:
        model = ExamCBCSync
        fields = [
            'id', 'exam', 'exam_name',
            'synced_by', 'synced_by_name',
            'synced_at', 'records_synced',
            'records_skipped',
        ]

    def get_synced_by_name(self, obj):
        return obj.synced_by.get_full_name() if obj.synced_by else None

    def get_exam_name(self, obj):
        return obj.exam.name
