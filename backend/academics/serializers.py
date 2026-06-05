from rest_framework import serializers

from students.models import Classroom

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


class LearningOutcomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningOutcome
        fields = ['id', 'sub_strand', 'description', 'order']


class SubStrandSerializer(serializers.ModelSerializer):
    outcomes = LearningOutcomeSerializer(many=True, read_only=True)

    class Meta:
        model = SubStrand
        fields = ['id', 'strand', 'name', 'order', 'outcomes']


class StrandSerializer(serializers.ModelSerializer):
    sub_strands = SubStrandSerializer(many=True, read_only=True)

    class Meta:
        model = Strand
        fields = ['id', 'subject', 'name', 'order', 'sub_strands']


class SubjectSerializer(serializers.ModelSerializer):
    strands = StrandSerializer(many=True, read_only=True)
    strand_count = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = [
            'id', 'name', 'code', 'description',
            'grade_levels', 'is_preloaded', 'is_active',
            'order', 'strands', 'strand_count',
        ]
        read_only_fields = ['is_preloaded']

    def get_strand_count(self, obj):
        return obj.strands.count()


class SubjectListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for subject dropdowns."""

    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'grade_levels', 'is_active', 'order']


class ClassSubjectAssignmentSerializer(serializers.ModelSerializer):
    subject_name = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    classroom_name = serializers.SerializerMethodField()

    class Meta:
        model = ClassSubjectAssignment
        fields = [
            'id', 'classroom', 'classroom_name',
            'subject', 'subject_name',
            'teacher', 'teacher_name',
            'academic_year', 'term',
        ]

    def get_subject_name(self, obj):
        return obj.subject.name

    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() if obj.teacher else None

    def get_classroom_name(self, obj):
        return str(obj.classroom)


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


class GenerateReportCardSerializer(serializers.Serializer):
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all())
    term = serializers.CharField()
    academic_year = serializers.IntegerField()
    report_type = serializers.ChoiceField(choices=['termly', 'annual'], default='termly')
    closing_date = serializers.DateField(required=False, allow_null=True)
    next_term_opening_date = serializers.DateField(required=False, allow_null=True)


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


class NationalExamSessionSerializer(serializers.ModelSerializer):
    classroom_name = serializers.SerializerMethodField()
    candidates_count = serializers.SerializerMethodField()
    registered_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = NationalExamSession
        fields = [
            'id', 'name', 'academic_year',
            'classroom', 'classroom_name',
            'centre_number', 'centre_name',
            'exam_date', 'is_results_entered',
            'notes', 'candidates_count',
            'registered_count',
            'created_by', 'created_by_name',
            'created_at',
        ]
        read_only_fields = ['created_by', 'created_at']

    def get_classroom_name(self, obj):
        return str(obj.classroom)

    def get_candidates_count(self, obj):
        return obj.candidates.count()

    def get_registered_count(self, obj):
        return obj.candidates.filter(is_registered=True).count()

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None


class NationalExamCandidateSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.SerializerMethodField()
    classroom_name = serializers.SerializerMethodField()

    class Meta:
        model = NationalExamCandidate
        fields = [
            'id', 'session', 'student',
            'student_name', 'admission_number',
            'classroom_name', 'index_number',
            'is_registered', 'registration_confirmed',
            'special_needs',
        ]

    def get_student_name(self, obj):
        return obj.student.get_full_name()

    def get_admission_number(self, obj):
        return obj.student.admission_number

    def get_classroom_name(self, obj):
        return str(obj.student.classroom) if obj.student.classroom else None


class NationalExamResultSerializer(serializers.ModelSerializer):
    subject_name = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = NationalExamResult
        fields = [
            'id', 'candidate', 'subject',
            'subject_name', 'student_name',
            'marks', 'total_marks',
            'grade', 'remarks',
        ]

    def get_subject_name(self, obj):
        return obj.subject.name

    def get_student_name(self, obj):
        return obj.candidate.student.get_full_name()
