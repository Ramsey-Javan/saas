import uuid
from decimal import Decimal

from django.db import models, transaction, IntegrityError
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from tenants.models import Tenant
from students.models import Student, Classroom
from accounts.models import CustomUser


class FeeStructure(models.Model):
    """Defines base fees per class, term, and academic year."""
    TERM_CHOICES = [
        ('term1', 'Term 1'), ('term2', 'Term 2'), ('term3', 'Term 3'), ('annual', 'Annual'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='fee_structures')
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='fee_structures')
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    academic_year = models.IntegerField()
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    late_penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    late_penalty_days = models.PositiveIntegerField(default=0, help_text="Grace period in days before penalty applies")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant', 'classroom', 'term', 'academic_year')
        ordering = ['-academic_year', 'term']

    def __str__(self):
        return f"{self.classroom.name} • {self.get_term_display()} {self.academic_year}"


CONFIRMED_PAYMENT_STATUSES = ('completed', 'confirmed')


class StudentFee(models.Model):
    """Tracks individual student fee obligations, balances, and status."""
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'), ('partial', 'Partial'), ('paid', 'Paid'),
        ('overdue', 'Overdue'), ('waived', 'Waived'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fees')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE)

    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    waived_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    carried_forward = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Arrears rolled from previous term")
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    due_date = models.DateField()

    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    waiver = models.ForeignKey('StudentWaiver', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    waiver_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def balance(self):
        total_paid = (
            self.payments.filter(status__in=CONFIRMED_PAYMENT_STATUSES)
            .aggregate(total=Coalesce(Sum('amount'), Value(Decimal('0.00')), output_field=DecimalField()))
            .get('total')
            or Decimal('0.00')
        )
        total_due = max(
            Decimal('0.00'),
            self.expected_amount + self.carried_forward + self.penalty_amount - self.waived_amount,
        )
        amount_paid = min(total_paid, total_due)
        return max(Decimal('0.00'), total_due - amount_paid)

    @property
    def overpayment(self):
        total_due = max(
            Decimal('0.00'),
            self.expected_amount + self.carried_forward + self.penalty_amount - self.waived_amount,
        )
        total_paid = (
            self.payments.filter(status__in=CONFIRMED_PAYMENT_STATUSES)
            .aggregate(total=Coalesce(Sum('amount'), Value(Decimal('0.00')), output_field=DecimalField()))
            .get('total')
            or Decimal('0.00')
        )
        return max(Decimal('0.00'), total_paid - total_due)

    @property
    def effective_balance(self):
        total_paid = (
            self.payments.filter(status__in=CONFIRMED_PAYMENT_STATUSES)
            .aggregate(total=Coalesce(Sum('amount'), Value(Decimal('0.00')), output_field=DecimalField()))
            .get('total')
            or Decimal('0.00')
        )
        amount_due = max(
            Decimal('0.00'),
            self.expected_amount + self.carried_forward + self.penalty_amount - self.waived_amount,
        )
        amount_paid = min(total_paid, amount_due)
        return max(Decimal('0.00'), amount_due - amount_paid)

    class Meta:
        unique_together = ('student', 'fee_structure')
        ordering = ['-fee_structure__academic_year', 'fee_structure__term']
        indexes = [
            models.Index(fields=['tenant', 'student', 'status']),
            models.Index(fields=['tenant', 'due_date']),
        ]

    def __str__(self):
        return f"{self.student.admission_number} • {self.fee_structure}"


class Payment(models.Model):
    """Records actual payments made by students."""
    METHOD_CHOICES = [
        ('mpesa', 'M-Pesa'), ('cash', 'Cash'), ('bank', 'Bank Transfer'), ('cheque', 'Cheque'), ('card', 'Card'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('completed', 'Completed'), ('confirmed', 'Confirmed'),
        ('failed', 'Failed'), ('expired', 'Expired'), ('reversed', 'Reversed'), ('bounced', 'Bounced'),
    ]
    DARAJA_RESULT_CODES = {
        '0': 'Success',
        '1': 'Insufficient funds',
        '1032': 'Cancelled by user',
        '1037': 'Timeout',
        '2006': 'Wrong PIN',
        '2001': 'Invalid parameters',
        '1001': 'Invalid number / Rejected',
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='payments')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    # SECURITY FIX #5: Changed from SET_NULL to PROTECT
    # Financial records must maintain referential integrity.
    # If an invoice needs deletion, all its payments must be handled first.
    student_fee = models.ForeignKey(StudentFee, on_delete=models.PROTECT, null=True, blank=True, related_name='payments')

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # M-Pesa specific
    mpesa_receipt_number = models.CharField(max_length=50, blank=True, db_index=True)
    mpesa_checkout_request_id = models.CharField(max_length=100, blank=True, db_index=True)
    mpesa_merchant_request_id = models.CharField(max_length=100, blank=True)
    mpesa_transaction_date = models.DateTimeField(null=True, blank=True)
    mpesa_result_code = models.CharField(
        max_length=10, blank=True, default='', db_index=True,
        help_text="Daraja result code from callback"
    )
    phone_number = models.CharField(max_length=15, blank=True, help_text="Normalized phone number used for STK push")

    # Manual payment details
    payment_date = models.DateField(null=True, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_reference = models.CharField(max_length=100, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    drawer_name = models.CharField(max_length=150, blank=True)

    # Idempotency & Audit
    idempotency_key = models.CharField(max_length=100, db_index=True, help_text="Prevents double-processing of callbacks")
    recorded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='recorded_payments')
    notes = models.TextField(blank=True)
    system_notes = models.TextField(blank=True, help_text="Internal processing notes")
    failure_reason = models.TextField(blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('tenant', 'idempotency_key')
        indexes = [
            models.Index(fields=['status', 'tenant']),
            models.Index(fields=['student', 'status']),
            models.Index(fields=['tenant', 'mpesa_checkout_request_id']),
            models.Index(fields=['tenant', 'mpesa_receipt_number']),
        ]

    def __str__(self):
        return f"Payment {self.amount} • {self.student.admission_number} • {self.status}"


class ReceiptCounter(models.Model):
    """
    Atomic counter for receipt number generation.
    Uses select_for_update() to prevent race conditions during concurrent payments.
    """
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='receipt_counter')
    last_number = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"ReceiptCounter {self.tenant.slug}: {self.last_number}"


class Receipt(models.Model):
    """Official receipt generated after successful payment."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='receipts')
    receipt_number = models.CharField(max_length=50, unique=True, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='receipt')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20)
    term = models.CharField(max_length=20)
    academic_year = models.CharField(max_length=9)
    issued_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            raw_code = (self.tenant.school_code or self.tenant.slug or 'SCH').strip()
            cleaned_code = ''.join(ch for ch in raw_code if ch.isalnum()).upper() or 'SCH'
            year = timezone.now().year

            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        counter, created = ReceiptCounter.objects.select_for_update().get_or_create(
                            tenant=self.tenant,
                            defaults={'last_number': 0}
                        )

                        # AUTO-HEAL: Sync counter with highest existing receipt for this year.
                        # Handles manual DB edits, migrations, or counter resets.
                        max_existing = Receipt._get_max_receipt_number(
                            self.tenant, cleaned_code, year
                        )
                        if max_existing is not None and max_existing > counter.last_number:
                            counter.last_number = max_existing

                        counter.last_number += 1
                        counter.save(update_fields=['last_number', 'updated_at'])
                        self.receipt_number = f"{cleaned_code}/{year}/{counter.last_number:03d}"

                    super().save(*args, **kwargs)
                    return

                except IntegrityError:
                    # Counter was out of sync — clear receipt_number and retry.
                    # Reset PK so Django treats this as a new insert on retry.
                    self.receipt_number = None
                    if self.pk:
                        self.pk = None
                    if attempt == max_retries - 1:
                        raise IntegrityError(
                            f"Failed to generate unique receipt number for tenant "
                            f"{self.tenant.slug} after {max_retries} attempts. "
                            f"Counter may be corrupted."
                        )

        else:
            super().save(*args, **kwargs)

    @staticmethod
    def _get_max_receipt_number(tenant, prefix, year):
        """Query the highest receipt sequence number for this tenant/year."""
        try:
            latest = Receipt.objects.filter(
                tenant=tenant,
                receipt_number__startswith=f"{prefix}/{year}/"
            ).order_by('-receipt_number').values_list('receipt_number', flat=True).first()

            if latest:
                parts = latest.split('/')
                if len(parts) == 3:
                    try:
                        return int(parts[2])
                    except (ValueError, IndexError):
                        pass
        except Exception:
            pass
        return 0

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f"Receipt {self.receipt_number} • {self.student.admission_number}"


class PaymentLog(models.Model):
    """Audit trail for every M-Pesa callback, query, and STK push attempt."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name='payment_logs')
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, null=True, blank=True, related_name='logs')
    checkout_request_id = models.CharField(max_length=100, blank=True, db_index=True)
    event_type = models.CharField(max_length=50, choices=[
        ('stk_push', 'STK Push'),
        ('callback', 'M-Pesa Callback'),
        ('status_query', 'Status Query'),
        ('expire', 'Auto Expire'),
        ('reconcile', 'Reconcile'),
        ('callback_orphan', 'Orphan Callback'),
    ])
    payload = models.JSONField(default=dict, blank=True)
    result_code = models.CharField(max_length=10, blank=True)
    result_desc = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['checkout_request_id', 'event_type']),
            models.Index(fields=['tenant', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} • {self.checkout_request_id} • {self.created_at}"


class WaiverPolicy(models.Model):
    """Defines waiver policies for different student categories."""
    CATEGORY_CHOICES = [
        ('full_waiver', 'Full Waiver'),
        ('staff_child', 'Staff Child'),
        ('bursary', 'Government Bursary'),
        ('sibling', 'Sibling Discount'),
        ('sponsor', 'Sponsor Support'),
        ('partial', 'Partial Waiver'),
        ('orphan', 'Orphan'),
    ]
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='waiver_policies')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    discount_type = models.CharField(max_length=50, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_waiver_policies')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant', 'category')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_category_display()} • {self.discount_value}{'' if self.discount_type == 'fixed' else '%'}"


class StudentWaiver(models.Model):
    """Tracks waivers assigned to individual students."""
    TERM_CHOICES = [
        ('term1', 'Term 1'),
        ('term2', 'Term 2'),
        ('term3', 'Term 3'),
        ('annual', 'Annual'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='student_waivers')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='waivers')
    policy = models.ForeignKey(WaiverPolicy, on_delete=models.PROTECT, related_name='student_waivers')
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='approved_waivers')
    approved_on = models.DateField(auto_now_add=True)
    valid_from_term = models.CharField(max_length=10, choices=TERM_CHOICES)
    valid_from_year = models.IntegerField()
    valid_until_term = models.CharField(max_length=10, choices=TERM_CHOICES, blank=True)
    valid_until_year = models.IntegerField(null=True, blank=True)
    supporting_document = models.FileField(upload_to='waiver_docs/', blank=True, null=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'policy')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.admission_number} • {self.policy.get_category_display()}"