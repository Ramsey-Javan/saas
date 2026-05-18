# backend/finance/serializers.py
from rest_framework import serializers
from .models import FeeStructure, StudentFee, Payment, Receipt, WaiverPolicy, StudentWaiver

class FeeStructureSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        request = self.context.get('request')
        tenant = getattr(request.user, 'tenant', None) if request else None
        if not tenant:
            return attrs

        if not self.instance:
            required_fields = ['classroom', 'term', 'academic_year', 'base_amount']
            missing = [field for field in required_fields if not attrs.get(field)]
            if missing:
                raise serializers.ValidationError({
                    'detail': f"Missing required fields: {', '.join(missing)}."
                })

        classroom = attrs.get('classroom') or getattr(self.instance, 'classroom', None)
        term = attrs.get('term') or getattr(self.instance, 'term', None)
        academic_year = attrs.get('academic_year') or getattr(self.instance, 'academic_year', None)

        if classroom and term and academic_year:
            existing = FeeStructure.objects.filter(
                tenant=tenant,
                classroom=classroom,
                term=term,
                academic_year=academic_year,
            )
            if self.instance:
                existing = existing.exclude(id=self.instance.id)
            if existing.exists():
                raise serializers.ValidationError(
                    {'detail': 'Fee structure already exists for this class, term, and academic year.'}
                )
        return attrs

    class Meta:
        model = FeeStructure
        fields = [
            'id', 'classroom', 'term', 'academic_year', 'base_amount', 'due_date',
            'late_penalty_amount', 'late_penalty_days', 'is_active', 'created_at'
        ]
        read_only_fields = ['tenant', 'created_at']

class StudentFeeSerializer(serializers.ModelSerializer):
    """Includes computed balance and nested student/classroom info for UI"""
    balance = serializers.SerializerMethodField()
    effective_balance = serializers.SerializerMethodField()
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    classroom_name = serializers.CharField(source='student.classroom.name', read_only=True)
    fee_term = serializers.CharField(source='fee_structure.term', read_only=True)
    fee_academic_year = serializers.CharField(source='fee_structure.academic_year', read_only=True)

    class Meta:
        model = StudentFee
        fields = [
            'id', 'student', 'student_name', 'admission_number', 'classroom_name',
            'fee_structure', 'fee_term', 'fee_academic_year', 'expected_amount', 'waived_amount', 'carried_forward',
            'penalty_amount', 'paid_amount', 'credit', 'balance', 'effective_balance', 'status', 'due_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['balance', 'tenant', 'created_at', 'updated_at']

    def get_balance(self, obj):
        # Balance exposed in UI must reflect effective balance after waivers and payments
        return obj.effective_balance

    def get_effective_balance(self, obj):
        return obj.effective_balance

class PaymentSerializer(serializers.ModelSerializer):
    receipt_number = serializers.CharField(source='receipt.receipt_number', read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    classroom_name = serializers.CharField(source='student.classroom.name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'student', 'student_fee', 'amount', 'payment_method', 'status',
            'mpesa_receipt_number', 'mpesa_checkout_request_id', 'mpesa_transaction_date',
            'payment_date', 'bank_name', 'bank_reference', 'cheque_number', 'drawer_name',
            'idempotency_key', 'recorded_by', 'notes', 'receipt_number',
            'student_name', 'admission_number', 'classroom_name', 'created_at'
        ]
        read_only_fields = ['tenant', 'status', 'recorded_by', 'created_at']

class ReceiptSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    
    class Meta:
        model = Receipt
        fields = '__all__'
        read_only_fields = ['tenant', 'receipt_number', 'issued_at']


class WaiverPolicySerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        discount_type = attrs.get('discount_type') or getattr(self.instance, 'discount_type', None)
        discount_value = attrs.get('discount_value')
        if discount_value is None and self.instance:
            discount_value = getattr(self.instance, 'discount_value', None)

        if discount_type == 'percentage' and discount_value is not None:
            if discount_value > 100:
                raise serializers.ValidationError({'discount_value': 'Percentage cannot exceed 100.'})
            if discount_value < 0:
                raise serializers.ValidationError({'discount_value': 'Percentage cannot be negative.'})

        if discount_value is not None and discount_value < 0:
            raise serializers.ValidationError({'discount_value': 'Discount value cannot be negative.'})

        return attrs

    class Meta:
        model = WaiverPolicy
        fields = [
            'id', 'category', 'discount_type', 'discount_value', 'is_active',
            'description', 'created_by', 'created_at'
        ]
        read_only_fields = ['tenant', 'created_by', 'created_at']


class StudentWaiverSerializer(serializers.ModelSerializer):
    policy_category = serializers.CharField(source='policy.get_category_display', read_only=True)
    policy_discount = serializers.SerializerMethodField()
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    classroom_name = serializers.CharField(source='student.classroom.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    invoice_original_amount = serializers.SerializerMethodField()
    invoice_waived_amount = serializers.SerializerMethodField()
    invoice_net_due = serializers.SerializerMethodField()
    invoice_paid = serializers.SerializerMethodField()
    invoice_balance = serializers.SerializerMethodField()
    supporting_document = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentWaiver
        fields = [
            'id', 'student', 'student_name', 'admission_number', 'classroom_name',
            'policy', 'policy_category', 'policy_discount',
            'approved_by', 'approved_by_name', 'approved_on',
            'valid_from_term', 'valid_from_year', 'valid_until_term', 'valid_until_year',
            'invoice_original_amount', 'invoice_waived_amount', 'invoice_net_due',
            'invoice_paid', 'invoice_balance',
            'supporting_document', 'notes', 'is_active', 'created_at'
        ]
        read_only_fields = ['tenant', 'approved_on', 'created_at']
    
    def get_policy_discount(self, obj):
        policy = obj.policy
        if policy.discount_type == 'percentage':
            return f"{policy.discount_value}%"
        return f"KES {policy.discount_value}"

    def get_supporting_document(self, obj):
        if not obj.supporting_document:
            return None
        request = self.context.get('request')
        url = obj.supporting_document.url
        if request:
            return request.build_absolute_uri(url)
        return url

    def _get_active_invoice(self, obj):
        from .models import StudentFee
        return StudentFee.objects.filter(
            student=obj.student,
            waiver=obj,
        ).order_by('-fee_structure__academic_year').first()

    def get_invoice_original_amount(self, obj):
        inv = self._get_active_invoice(obj)
        return str(inv.expected_amount) if inv else '0.00'

    def get_invoice_waived_amount(self, obj):
        inv = self._get_active_invoice(obj)
        return str(inv.waived_amount) if inv else '0.00'

    def get_invoice_net_due(self, obj):
        from decimal import Decimal
        inv = self._get_active_invoice(obj)
        if not inv:
            return '0.00'
        net = max(
            Decimal('0'),
            inv.expected_amount + inv.carried_forward + inv.penalty_amount - inv.waived_amount
        )
        return str(net)

    def get_invoice_paid(self, obj):
        inv = self._get_active_invoice(obj)
        return str(inv.paid_amount) if inv else '0.00'

    def get_invoice_balance(self, obj):
        inv = self._get_active_invoice(obj)
        return str(inv.balance) if inv else '0.00'

