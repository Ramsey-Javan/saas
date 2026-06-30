"""National exam serializers."""
from rest_framework import serializers

from ..models import (
    NationalExamCandidate,
    NationalExamResult,
    NationalExamSession,
)


class NationalExamSessionSerializer(serializers.ModelSerializer):
    classroom_name = serializers.SerializerMethodField()
    grade_level = serializers.SerializerMethodField()
    candidates_count = serializers.SerializerMethodField()
    registered_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = NationalExamSession
        fields = [
            'id', 'name', 'academic_year',
            'classroom', 'classroom_name', 'grade_level',
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

    def get_grade_level(self, obj):
        return obj.classroom.grade_level if obj.classroom else ''

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