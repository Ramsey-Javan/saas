from django.contrib import admin
from .models import FeeStructure, FeePayment, MpesaTransaction


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['grade_level', 'fee_type', 'term', 'academic_year', 'amount', 'is_mandatory']
    list_filter = ['academic_year', 'term', 'grade_level', 'fee_type', 'is_mandatory']
    search_fields = ['grade_level', 'description']
    ordering = ['academic_year', 'term', 'grade_level', 'fee_type']


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'amount_paid', 'balance', 'payment_method',
        'transaction_ref', 'term', 'academic_year', 'status', 'payment_date',
    ]
    list_filter = ['payment_method', 'status', 'term', 'academic_year']
    search_fields = [
        'student__first_name', 'student__last_name', 'student__admission_number', 'transaction_ref',
    ]
    readonly_fields = ['payment_date']
    autocomplete_fields = ['student']


@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'phone_number', 'amount', 'mpesa_receipt_number', 'status',
        'account_reference', 'created_at',
    ]
    list_filter = ['status']
    search_fields = ['phone_number', 'mpesa_receipt_number', 'checkout_request_id', 'account_reference']
    readonly_fields = ['created_at', 'updated_at']
