from django.contrib import admin
from .models import FeeStructure, Payment, Receipt, StudentFee


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = (
        'classroom',
        'term',
        'academic_year',
        'base_amount',
        'late_penalty_amount',
        'tenant',
        'is_active',
    )
    list_filter = ('tenant', 'term', 'academic_year', 'is_active')
    search_fields = ('classroom__name', 'academic_year')
    readonly_fields = ('created_at',)


@admin.register(StudentFee)
class StudentFeeAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'fee_structure',
        'expected_amount',
        'paid_amount',
        'credit',
        'waived_amount',
        'carried_forward',
        'penalty_amount',
        'status',
        'due_date',
    )
    list_filter = ('tenant', 'status', 'fee_structure__term', 'fee_structure__academic_year')
    search_fields = ('student__admission_number', 'student__first_name', 'student__last_name')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'amount',
        'payment_method',
        'status',
        'mpesa_receipt_number',
        'recorded_by',
        'created_at',
    )
    list_filter = ('tenant', 'payment_method', 'status', 'created_at')
    search_fields = (
        'student__admission_number',
        'student__first_name',
        'student__last_name',
        'mpesa_receipt_number',
        'mpesa_checkout_request_id',
        'idempotency_key',
    )
    readonly_fields = (
        'id',
        'idempotency_key',
        'mpesa_receipt_number',
        'mpesa_checkout_request_id',
        'mpesa_transaction_date',
        'created_at',
    )


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = (
        'receipt_number',
        'student',
        'amount',
        'payment_method',
        'term',
        'academic_year',
        'issued_by',
        'issued_at',
    )
    list_filter = ('tenant', 'payment_method', 'term', 'academic_year', 'issued_at')
    search_fields = ('receipt_number', 'student__admission_number', 'student__first_name', 'student__last_name')
    readonly_fields = ('receipt_number', 'issued_at')
