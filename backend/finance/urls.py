from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FeeStructureViewSet, MpesaViewSet, PaymentViewSet, ReceiptViewSet,
    StudentFeeViewSet, WaiverPolicyViewSet, StudentWaiverViewSet,
    student_statement, bulk_invoice_pdf, bulk_sms, bulk_receipts_pdf,
    student_statement_pdf, bulk_statement_pdf
)

router = DefaultRouter()
router.register(r'fee-structures', FeeStructureViewSet, basename='fee-structure')
router.register(r'structures', FeeStructureViewSet, basename='structure')
router.register(r'student-fees', StudentFeeViewSet, basename='student-fee')
router.register(r'invoices', StudentFeeViewSet, basename='invoice')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'receipts', ReceiptViewSet, basename='receipt')
router.register(r'mpesa', MpesaViewSet, basename='mpesa')
router.register(r'waiver-policies', WaiverPolicyViewSet, basename='waiver-policy')
router.register(r'waivers', StudentWaiverViewSet, basename='waiver')

urlpatterns = [
    path('invoices/bulk-pdf/', bulk_invoice_pdf, name='invoice-bulk-pdf'),
    path('invoices/bulk-sms/', bulk_sms, name='invoice-bulk-sms'),
    path('receipts/bulk-pdf/', bulk_receipts_pdf, name='receipt-bulk-pdf'),
    path('students/<int:student_id>/statement/', student_statement, name='student-statement'),
    path('students/<int:student_id>/statement/pdf/', student_statement_pdf, name='student-statement-pdf'),
    path('students/statements/bulk-pdf/', bulk_statement_pdf, name='student-statement-bulk-pdf'),
    path('invoices/generate_bulk/', StudentFeeViewSet.as_view({'post': 'generate_bulk'}), name='invoice-generate-bulk'),
    path('', include(router.urls)),
]
