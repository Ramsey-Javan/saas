from rest_framework import serializers

from .models import Classroom, Guardian, Student


class ClassroomSerializer(serializers.ModelSerializer):
    student_count = serializers.ReadOnlyField()
    class_teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Classroom
        fields = [
            'id', 'name', 'grade_level', 'stream', 'class_teacher',
            'class_teacher_name', 'academic_year', 'capacity', 'student_count',
        ]

    def get_class_teacher_name(self, obj):
        return obj.class_teacher.get_full_name() if obj.class_teacher else None


class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = [
            'id', 'first_name', 'last_name', 'phone', 'alt_phone',
            'email', 'relationship', 'national_id', 'occupation', 'user',
        ]
        read_only_fields = ['user']


class StudentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    full_name = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()  # Replaces raw FK + classroom_name
    guardian_phone = serializers.SerializerMethodField()
    age = serializers.ReadOnlyField()

    class Meta:
        model = Student
        fields = [
            'id', 'admission_number', 'full_name', 'first_name', 'last_name',
            'gender', 'classroom', 'status',
            'guardian_phone', 'age', 'photo',
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_classroom(self, obj):
        """Return a lightweight classroom object instead of a raw ID."""
        if not obj.classroom:
            return None
        return {
            'id': obj.classroom.id,
            'name': obj.classroom.name,
            'stream': obj.classroom.stream,
            'academic_year': obj.classroom.academic_year,
        }

    def get_guardian_phone(self, obj):
        return obj.primary_guardian.phone if obj.primary_guardian else None

class StudentDetailSerializer(serializers.ModelSerializer):
    """Full serializer for create/retrieve/update."""
    full_name = serializers.SerializerMethodField()
    age = serializers.ReadOnlyField()
    primary_guardian_data = GuardianSerializer(source='primary_guardian', read_only=True)
    classroom_data = ClassroomSerializer(source='classroom', read_only=True)
    guardian = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = Student
        fields = [
            'id', 'admission_number', 'first_name', 'middle_name', 'last_name',
            'full_name', 'gender', 'date_of_birth', 'age',
            'birth_certificate_no', 'nemis_no', 'photo',
            'classroom', 'classroom_data',
            'admission_date', 'status', 'is_active',
            'primary_guardian', 'primary_guardian_data',
            'blood_group', 'medical_notes', 'special_needs',
            'created_at', 'updated_at', 'guardian',
        ]
        read_only_fields = [
            'created_at',
            'updated_at',
            'admission_date',
            'status',
            'is_active',
            'age',
            'full_name',
            'primary_guardian_data',
            'classroom_data',
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()

    def validate_admission_number(self, value):
        qs = Student.objects.filter(admission_number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('This admission number is already in use.')
        return value

    def validate_guardian(self, value):
        if not value:
            return value
        required = ['first_name', 'last_name', 'phone', 'relationship']
        missing = [f for f in required if not value.get(f)]
        if missing:
            raise serializers.ValidationError(
                {f: 'This field is required.' for f in missing}
            )
        return value

    def update(self, instance, validated_data):
        guardian_data = validated_data.pop('guardian', None)
        student = super().update(instance, validated_data)

        if guardian_data:
            if student.primary_guardian:
                g = student.primary_guardian
                for attr, val in guardian_data.items():
                    if val is not None:
                        setattr(g, attr, val)
                g.save()
            else:
                g = Guardian.objects.create(
                    tenant=student.tenant,
                    **guardian_data
                )
                student.primary_guardian = g
                student.save(update_fields=['primary_guardian'])

        return student
