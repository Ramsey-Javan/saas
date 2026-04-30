from rest_framework import serializers
from .models import AttendanceRecord


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'student', 'student_name', 'student_admission',
            'date', 'status', 'recorded_by', 'recorded_by_name',
            'remarks', 'created_at',
        ]
        read_only_fields = ['created_at', 'recorded_by']

    def create(self, validated_data):
        validated_data['recorded_by'] = self.context['request'].user
        return super().create(validated_data)


class BulkAttendanceSerializer(serializers.Serializer):
    date = serializers.DateField()
    records = serializers.ListField(
        child=serializers.DictField(),
        help_text='List of {student_id, status, remarks} dicts',
    )

    def validate_records(self, value):
        for record in value:
            if 'student_id' not in record or 'status' not in record:
                raise serializers.ValidationError("Each record must have 'student_id' and 'status'.")
            valid_statuses = [s[0] for s in AttendanceRecord.STATUS_CHOICES]
            if record['status'] not in valid_statuses:
                raise serializers.ValidationError(
                    f"Invalid status '{record['status']}'. Choose from {valid_statuses}."
                )
        return value


class AttendanceSummarySerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    admission_number = serializers.CharField()
    total_days = serializers.IntegerField()
    present = serializers.IntegerField()
    absent = serializers.IntegerField()
    late = serializers.IntegerField()
    excused = serializers.IntegerField()
    half_day = serializers.IntegerField()
    attendance_percentage = serializers.FloatField()
