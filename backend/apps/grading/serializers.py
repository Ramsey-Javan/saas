from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Subject, Assessment, ReportCard, COMPETENCY_CHOICES


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'grade_level', 'description', 'is_active']


class AssessmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True)
    competency_display = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id', 'student', 'student_name', 'subject', 'subject_name',
            'term', 'academic_year', 'assessment_type', 'competency', 'competency_display',
            'marks', 'max_marks', 'teacher_remarks', 'assessment_date',
            'recorded_by', 'recorded_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'recorded_by']

    @extend_schema_field(serializers.CharField())
    def get_competency_display(self, obj):
        return obj.competency_display

    def create(self, validated_data):
        validated_data['recorded_by'] = self.context['request'].user
        return super().create(validated_data)


class AssessmentBulkSerializer(serializers.Serializer):
    assessments = AssessmentSerializer(many=True)

    def create(self, validated_data):
        items = validated_data['assessments']
        user = self.context['request'].user
        objs = [Assessment(recorded_by=user, **item) for item in items]
        return Assessment.objects.bulk_create(objs)


class ReportCardSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    assessments = serializers.SerializerMethodField()

    class Meta:
        model = ReportCard
        fields = [
            'id', 'student', 'student_name', 'term', 'academic_year',
            'class_teacher_remarks', 'principal_remarks', 'next_term_opening_date',
            'status', 'generated_by', 'assessments', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'generated_by']

    @extend_schema_field(AssessmentSerializer(many=True))
    def get_assessments(self, obj):
        qs = Assessment.objects.filter(
            student=obj.student, term=obj.term, academic_year=obj.academic_year
        )
        return AssessmentSerializer(qs, many=True).data

    def create(self, validated_data):
        validated_data['generated_by'] = self.context['request'].user
        return super().create(validated_data)


class StudentCompetencySummarySerializer(serializers.Serializer):
    subject_name = serializers.CharField()
    competency = serializers.CharField()
    competency_display = serializers.CharField()
    assessment_type = serializers.CharField()
    assessment_date = serializers.DateField()
