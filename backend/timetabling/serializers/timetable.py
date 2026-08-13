from rest_framework import serializers

from ..models import TimetableEntry, TimetableJob


class TimetableJobSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TimetableJob
        fields = [
            'id', 'term', 'academic_year', 'status', 'created_by',
            'created_by_name', 'current_score', 'best_bound', 'failure_reason',
            'solve_time_seconds', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'status', 'created_by', 'created_by_name', 'current_score',
            'best_bound', 'failure_reason', 'solve_time_seconds',
            'created_at', 'updated_at','published','published_at'
        ]

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None


class TimetableEntrySerializer(serializers.ModelSerializer):
    classroom_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    room_name = serializers.CharField(source='room.name', read_only=True, allow_null=True)
    period_label = serializers.SerializerMethodField()
    day_of_week = serializers.IntegerField(source='period.day_of_week', read_only=True)
    period_order = serializers.IntegerField(source='period.order', read_only=True)
    start_time = serializers.TimeField(source='period.start_time', read_only=True)
    end_time = serializers.TimeField(source='period.end_time', read_only=True)

    class Meta:
        model = TimetableEntry
        fields = [
            'id', 'job', 'classroom', 'classroom_name', 'subject', 'subject_name',
            'teacher', 'teacher_name', 'period', 'period_label', 'day_of_week',
            'period_order', 'start_time', 'end_time', 'room', 'room_name', 'locked',
        ]
        read_only_fields = ['locked']

    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() or obj.teacher.email

    def get_classroom_name(self, obj):
        return str(obj.classroom)

    def get_period_label(self, obj):
        return str(obj.period)


class TimetableEntryUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableEntry
        fields = ['classroom', 'subject', 'teacher', 'period', 'room']


class PartialRegenerateSerializer(serializers.Serializer):
    class_stream_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)

class CopyTimetableSerializer(serializers.Serializer):
    source_term = serializers.ChoiceField(choices=TimetableJob._meta.get_field('term').choices)
    source_academic_year = serializers.IntegerField(min_value=2000, max_value=2100)
    target_term = serializers.ChoiceField(choices=TimetableJob._meta.get_field('term').choices)
    target_academic_year = serializers.IntegerField(min_value=2000, max_value=2100)

    def validate(self, attrs):
        if attrs['source_term'] == attrs['target_term'] and attrs['source_academic_year'] == attrs['target_academic_year']:
            raise serializers.ValidationError('Source and target term/year must be different.')
        return attrs