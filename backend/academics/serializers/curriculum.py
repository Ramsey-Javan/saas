"""Curriculum serializers."""
from rest_framework import serializers

from ..models import (
    ClassSubjectAssignment,
    LearningOutcome,
    Strand,
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
