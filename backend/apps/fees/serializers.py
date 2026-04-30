from rest_framework import serializers
from decimal import Decimal
from .models import FeeStructure, FeePayment, MpesaTransaction


class FeeStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        fields = [
            'id', 'grade_level', 'term', 'academic_year', 'fee_type',
            'amount', 'description', 'is_mandatory', 'due_date',
        ]


class FeePaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_admission = serializers.CharField(source='student.admission_number', read_only=True)

    class Meta:
        model = FeePayment
        fields = [
            'id', 'student', 'student_name', 'student_admission',
            'fee_structure', 'amount_paid', 'balance', 'payment_date',
            'payment_method', 'transaction_ref', 'term', 'academic_year',
            'status', 'notes', 'received_by',
        ]
        read_only_fields = ['payment_date']


class FeePaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeePayment
        fields = [
            'student', 'fee_structure', 'amount_paid', 'balance',
            'payment_method', 'transaction_ref', 'term', 'academic_year',
            'status', 'notes', 'received_by',
        ]


class MpesaTransactionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)

    class Meta:
        model = MpesaTransaction
        fields = [
            'id', 'phone_number', 'amount', 'merchant_request_id',
            'checkout_request_id', 'result_code', 'result_desc',
            'mpesa_receipt_number', 'transaction_date', 'status',
            'student', 'student_name', 'account_reference', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class StkPushSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1'))
    student_id = serializers.IntegerField()
    account_reference = serializers.CharField(max_length=12)
    transaction_desc = serializers.CharField(max_length=13, required=False, default='School Fees')

    def validate_phone_number(self, value):
        phone = str(value).strip().replace('+', '').replace(' ', '')
        if not phone.isdigit():
            raise serializers.ValidationError('Phone number must contain digits only.')
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        if not phone.startswith('254') or len(phone) != 12:
            raise serializers.ValidationError('Enter a valid Kenyan phone number (e.g. 0712345678 or 254712345678).')
        return phone


class StudentFeeBalanceSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(read_only=True)
    admission_number = serializers.CharField(read_only=True)
    student_name = serializers.CharField(read_only=True)
    term = serializers.CharField(read_only=True)
    academic_year = serializers.CharField(read_only=True)
    total_expected = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
