from rest_framework import serializers
from .models import SMSLog


class SMSLogSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    sent_by_name = serializers.CharField(source='sent_by.full_name', read_only=True)

    class Meta:
        model = SMSLog
        fields = [
            'id', 'recipient_phone', 'message', 'student', 'student_name',
            'sent_by', 'sent_by_name', 'status', 'sent_at', 'provider_response',
            'message_id', 'created_at',
        ]
        read_only_fields = ['status', 'sent_at', 'provider_response', 'message_id', 'created_at']


class SendSMSSerializer(serializers.Serializer):
    phone_numbers = serializers.ListField(
        child=serializers.CharField(max_length=15),
        min_length=1,
    )
    message = serializers.CharField(max_length=1600)
    student_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_phone_numbers(self, value):
        cleaned = []
        for phone in value:
            p = str(phone).strip().replace(' ', '').replace('-', '')
            if not p:
                continue
            cleaned.append(p)
        if not cleaned:
            raise serializers.ValidationError('At least one valid phone number is required.')
        return cleaned


class BulkSMSSerializer(serializers.Serializer):
    grade_level = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField(max_length=1600)
    send_to = serializers.ChoiceField(
        choices=[('all', 'All Students'), ('grade', 'Specific Grade'), ('debtors', 'Fee Defaulters')],
        default='all',
    )
    term = serializers.CharField(required=False, allow_blank=True)
    academic_year = serializers.CharField(required=False, allow_blank=True)
