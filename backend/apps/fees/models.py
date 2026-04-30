from django.db import models
from apps.students.models import Student


class FeeStructure(models.Model):
    TERM_CHOICES = [
        ('term1', 'Term 1'),
        ('term2', 'Term 2'),
        ('term3', 'Term 3'),
    ]

    FEE_TYPE_CHOICES = [
        ('tuition', 'Tuition'),
        ('boarding', 'Boarding'),
        ('lunch', 'Lunch'),
        ('activity', 'Activity'),
        ('uniform', 'Uniform'),
        ('books', 'Books & Materials'),
        ('transport', 'Transport'),
        ('exam', 'Examination'),
        ('other', 'Other'),
    ]

    grade_level = models.CharField(max_length=5)
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=9, help_text='e.g. 2024/2025')
    fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    is_mandatory = models.BooleanField(default=True)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Fee Structure'
        verbose_name_plural = 'Fee Structures'
        ordering = ['academic_year', 'term', 'grade_level', 'fee_type']
        unique_together = ['grade_level', 'term', 'academic_year', 'fee_type']

    def __str__(self):
        return f'{self.grade_level} - {self.fee_type} - {self.term} {self.academic_year}: KES {self.amount}'


class FeePayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('mpesa', 'M-Pesa'),
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('cheque', 'Cheque'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('partial', 'Partial'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]

    TERM_CHOICES = [
        ('term1', 'Term 1'),
        ('term2', 'Term 2'),
        ('term3', 'Term 3'),
    ]

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='fee_payments')
    fee_structure = models.ForeignKey(
        FeeStructure, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments'
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    transaction_ref = models.CharField(max_length=100, blank=True)
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=9)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    received_by = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'Fee Payment'
        verbose_name_plural = 'Fee Payments'
        ordering = ['-payment_date']

    def __str__(self):
        return f'{self.student} - KES {self.amount_paid} ({self.payment_method}) - {self.term} {self.academic_year}'


class MpesaTransaction(models.Model):
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('timeout', 'Timeout'),
    ]

    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, db_index=True)
    result_code = models.IntegerField(null=True, blank=True)
    result_desc = models.CharField(max_length=255, blank=True)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    transaction_date = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    student = models.ForeignKey(
        Student, on_delete=models.SET_NULL, null=True, blank=True, related_name='mpesa_transactions'
    )
    fee_payment = models.OneToOneField(
        FeePayment, on_delete=models.SET_NULL, null=True, blank=True, related_name='mpesa_transaction'
    )
    account_reference = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'M-Pesa Transaction'
        verbose_name_plural = 'M-Pesa Transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.phone_number} - KES {self.amount} - {self.status} ({self.mpesa_receipt_number or self.checkout_request_id})'
