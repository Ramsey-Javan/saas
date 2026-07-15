import re
from decimal import Decimal
from rest_framework import serializers

from .models import (
    FeeStructure, 
    StudentFee, 
    Payment, 
    Receipt, 
    WaiverPolicy, 
    StudentWaiver,
    PaymentLog,
)


# ==========================================
# 1. FEE STRUCTURE SERIALIZER
# ==========================================
class FeeStructureSerializer(serializers.ModelSerializer):
    # Fields that determine how much a student owes. Once any invoice has
    # been generated from this fee structure, these are locked -- editing
    # them must never retroactively change an already-billed invoice. To
    # change a fee mid-year, create a NEW FeeStructure for the next term
    # instead (e.g. "from Term 2, fees increase to X").
    LOCKED_AFTER_INVOICING = ['base_amount', 'late_penalty_amount', 'late_penalty_days']

    class Meta:
        model = FeeStructure
        fields = [
            'id', 'classroom', 'term', 'academic_year', 'base_amount', 'due_date',
            'late_penalty_amount', 'late_penalty_days', 'is_active', 'created_at'
        ]
        read_only_fields = ('id', 'tenant', 'created_at')

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

        # LOCK base_amount / late_penalty_amount / late_penalty_days once
        # invoices have been generated against this fee structure. due_date
        # and is_active remain freely editable since they don't change what
        # a student is billed.
        if self.instance and StudentFee.objects.filter(fee_structure=self.instance).exists():
            changed_locked_fields = [
                field for field in self.LOCKED_AFTER_INVOICING
                if field in attrs and attrs[field] != getattr(self.instance, field)
            ]
            if changed_locked_fields:
                raise serializers.ValidationError({
                    'detail': (
                        f"Cannot change {', '.join(changed_locked_fields)} -- this fee "
                        "structure already has invoices generated against it. Changing the "
                        "amount now would not update those existing invoices, and would be "
                        "confusing/inaccurate for already-billed students. Create a new fee "
                        "structure for the next term instead (e.g. 'From Term 2, fees "
                        "increase to KES X')."
                    )
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


# ==========================================
# 2. STUDENT FEE SERIALIZER
# ==========================================
class StudentFeeSerializer(serializers.ModelSerializer):
    """Includes computed balance and nested student/classroom info for UI"""
    balance = serializers.SerializerMethodField()
    overpayment = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
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
            'penalty_amount', 'paid_amount', 'credit', 'balance', 'overpayment', 'effective_balance', 'status', 'due_date',
            'created_at', 'updated_at', 'tenant'
        ]
        read_only_fields = ('id', 'tenant', 'created_at', 'updated_at', 'paid_amount', 'balance', 'effective_balance')

    def get_balance(self, obj):
        # Balance exposed in UI must reflect effective balance after waivers and payments
        return obj.effective_balance

    def get_effective_balance(self, obj):
        return obj.effective_balance


# ==========================================
# 3. PAYMENT LOG SERIALIZER
# ==========================================
class PaymentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentLog
        fields = ['id', 'event_type', 'result_code', 'result_desc', 'created_at', 'payload']
        read_only_fields = fields


# ==========================================
# 4. PAYMENT SERIALIZER
# ==========================================
class PaymentSerializer(serializers.ModelSerializer):
    logs = PaymentLogSerializer(many=True, read_only=True)
    receipt_number = serializers.CharField(source='receipt.receipt_number', read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    classroom_name = serializers.CharField(source='student.classroom.name', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'student', 'student_fee', 'amount', 'payment_method', 'status',
            'mpesa_receipt_number', 'mpesa_checkout_request_id', 'mpesa_merchant_request_id',
            'mpesa_transaction_date', 'payment_date', 'bank_name', 'bank_reference', 
            'cheque_number', 'drawer_name', 'idempotency_key', 'recorded_by', 'notes', 
            'receipt_number', 'student_name', 'admission_number', 'classroom_name', 
            'resolved_at', 'failed_at', 'system_notes', 'created_at', 'tenant', 'logs'
        ]
        read_only_fields = (
            'id', 'tenant', 'status', 'recorded_by', 'created_at', 
            'mpesa_checkout_request_id', 'mpesa_receipt_number', 
            'mpesa_merchant_request_id', 'resolved_at', 'failed_at', 'system_notes'
        )


# ==========================================
# 5. RECEIPT SERIALIZER
# ==========================================
class ReceiptSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)

    class Meta:
        model = Receipt
        fields = '__all__'
        read_only_fields = ('id', 'tenant', 'receipt_number', 'issued_at')


# ==========================================
# 6. WAIVER POLICY SERIALIZER
# ==========================================
class WaiverPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = WaiverPolicy
        fields = [
            'id', 'category', 'discount_type', 'discount_value', 'is_active',
            'description', 'created_by', 'created_at', 'tenant'
        ]
        read_only_fields = ('id', 'tenant', 'created_by', 'created_at')

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


# ==========================================
# 7. STUDENT WAIVER SERIALIZER
# ==========================================
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
            'supporting_document', 'notes', 'is_active', 'created_at', 'tenant'
        ]
        read_only_fields = ('id', 'tenant', 'created_at', 'approved_on')

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
        # Local import to prevent potential circular import flags
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


# ==========================================
# 8. MPESA INITIATE SERIALIZER (Standard Serializer)
# ==========================================
class MpesaInitiateSerializer(serializers.Serializer):
    """
    Validates and normalizes M-Pesa STK push initiation data.

    SECURITY FIX #9: Phone validation now handles +254 prefix consistently
    with frontend validatePhone() function.

    SECURITY FIX #14: Supports client-generated idempotency_key for true
    idempotency across retries.
    """
    phone = serializers.CharField(max_length=20, required=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=True, min_value=1)
    student_id = serializers.UUIDField(required=True)
    fee_id = serializers.UUIDField(required=False, allow_null=True)
    idempotency_key = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_phone(self, value):
        """
        Normalize phone to 2547XXXXXXXX.
        Handles: 07XX XXX XXX, 7XX XXX XXX, 2547XX XXX XXX, +2547XX XXX XXX
        """
        if not value:
            raise serializers.ValidationError("Phone number is required.")

        # Remove all non-digits, including + prefix
        digits = re.sub(r'\D', '', str(value))

        # Handle +254 prefix (already stripped by regex, but double-check)
        if digits.startswith('254') and len(digits) == 12:
            pass  # Already correct format
        elif digits.startswith('0') and len(digits) == 10:
            digits = '254' + digits[1:]
        elif digits.startswith('7') and len(digits) == 9:
            digits = '254' + digits
        elif digits.startswith('254') and len(digits) == 13:
            # Edge case: someone typed 2540... treat as 0-prefixed
            digits = '254' + digits[3:]
        else:
            raise serializers.ValidationError(
                "Invalid Kenyan phone number. Use format 07XX XXX XXX, 2547XX XXX XXX, or +2547XX XXX XXX."
            )

        # Validate Safaricom prefix (7xx, 1xx for new prefixes)
        if not re.match(r'^254[71]\d{8}$', digits):
            raise serializers.ValidationError("Invalid Kenyan mobile number format.")

        return digits

    def validate_amount(self, value):
        if value < 1:
            raise serializers.ValidationError("Amount must be at least 1 KES.")
        if value > 150000:
            raise serializers.ValidationError("Amount exceeds M-Pesa limit of 150,000 KES.")
        return value

    def validate_idempotency_key(self, value):
        """Sanitize idempotency key to prevent injection."""
        if value:
            # Strip whitespace and limit length
            value = value.strip()[:100]
            # Only allow alphanumeric, hyphens, underscores
            if not re.match(r'^[a-zA-Z0-9_-]+$', value):
                raise serializers.ValidationError(
                    "Idempotency key must contain only letters, numbers, hyphens, and underscores."
                )
        return value
    