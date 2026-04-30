from django.contrib import admin
from .models import FeeStructure, Payment, MPesaTransaction


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'amount', 'is_active')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'student', 'amount', 'status', 'method')


@admin.register(MPesaTransaction)
class MPesaTransactionAdmin(admin.ModelAdmin):
    list_display = ('mpesa_code', 'phone_number', 'payment')
