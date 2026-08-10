from rest_framework import serializers

from ..models import (
    Period,
    RoomResource,
    ScheduleTemplate,
    SubjectRule,
    TeacherAvailability,
    TeacherSubjectAssignment,
    TeacherWorkloadLimit,
)


class ScheduleTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleTemplate
        fields = ['id', 'name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class PeriodSerializer(serializers.ModelSerializer):
    schedule_template_name = serializers.CharField(source='schedule_template.name', read_only=True)
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = Period
        fields = [
            'id', 'schedule_template', 'schedule_template_name',
            'day_of_week', 'day_name', 'order', 'start_time', 'end_time', 'is_break',
        ]


class RoomResourceSerializer(serializers.ModelSerializer):
    room_type_label = serializers.CharField(source='get_room_type_display', read_only=True)

    class Meta:
        model = RoomResource
        fields = ['id', 'name', 'room_type', 'room_type_label', 'capacity', 'is_active']


class SubjectRuleSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = SubjectRule
        fields = [
            'id', 'subject', 'subject_name', 'grade_band', 'stream', 'periods_per_week',
            'requires_double', 'requires_room_type', 'excluded_periods',
            'is_hard_excluded', 'time_preference', 'is_active',
        ]


class TeacherAvailabilitySerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    period_label = serializers.SerializerMethodField()

    class Meta:
        model = TeacherAvailability
        fields = ['id', 'teacher', 'teacher_name', 'period', 'period_label', 'is_available']

    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() or obj.teacher.email

    def get_period_label(self, obj):
        return str(obj.period)


class TeacherWorkloadLimitSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = TeacherWorkloadLimit
        fields = ['id', 'teacher', 'teacher_name', 'max_periods_per_day', 'max_periods_per_week']

    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() or obj.teacher.email


class TeacherSubjectAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    classroom_name = serializers.SerializerMethodField()

    class Meta:
        model = TeacherSubjectAssignment
        fields = [
            'id', 'teacher', 'teacher_name', 'subject', 'subject_name',
            'classroom', 'classroom_name',
        ]

    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() or obj.teacher.email

    def get_classroom_name(self, obj):
        return str(obj.classroom)


class BulkTeacherSubjectAssignmentSerializer(serializers.Serializer):
    teacher = serializers.IntegerField()
    subject = serializers.IntegerField()
    classrooms = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    