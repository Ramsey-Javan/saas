from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Student, Admission, GRADE_CHOICES


class AdmissionSerializer(serializers.ModelSerializer):
    admitted_by_name = serializers.CharField(source='admitted_by.full_name', read_only=True)

    class Meta:
        model = Admission
        fields = [
            'id', 'student', 'academic_year', 'date_admitted', 'admission_type',
            'previous_school', 'grade_on_admission', 'status', 'notes',
            'admitted_by', 'admitted_by_name', 'created_at',
        ]
        read_only_fields = ['created_at', 'admitted_by']

    def create(self, validated_data):
        validated_data['admitted_by'] = self.context['request'].user
        return super().create(validated_data)


class StudentListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    grade_display = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'admission_number', 'full_name', 'first_name', 'last_name',
            'grade_level', 'grade_display', 'stream', 'gender', 'is_active', 'photo',
        ]

    @extend_schema_field(serializers.CharField())
    def get_full_name(self, obj):
        return obj.full_name

    @extend_schema_field(serializers.CharField())
    def get_grade_display(self, obj):
        return obj.grade_display


class StudentDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    grade_display = serializers.SerializerMethodField()
    admissions = AdmissionSerializer(many=True, read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'first_name', 'last_name', 'other_names', 'full_name',
            'admission_number', 'date_of_birth', 'gender', 'grade_level', 'grade_display',
            'stream', 'photo', 'is_active',
            'parent_name', 'parent_phone', 'parent_email', 'parent_relationship',
            'parent_occupation', 'parent_address',
            'secondary_contact_name', 'secondary_contact_phone',
            'admissions', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    @extend_schema_field(serializers.CharField())
    def get_full_name(self, obj):
        return obj.full_name

    @extend_schema_field(serializers.CharField())
    def get_grade_display(self, obj):
        return obj.grade_display


class StudentCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'other_names', 'admission_number',
            'date_of_birth', 'gender', 'grade_level', 'stream', 'photo', 'is_active',
            'parent_name', 'parent_phone', 'parent_email', 'parent_relationship',
            'parent_occupation', 'parent_address',
            'secondary_contact_name', 'secondary_contact_phone',
        ]
