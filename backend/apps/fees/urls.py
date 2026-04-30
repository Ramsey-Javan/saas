from django.urls import path
from .views import (
    FeeStructureListCreateView,
    FeeStructureDetailView,
    FeePaymentListCreateView,
    FeePaymentDetailView,
    StudentPaymentsView,
    StkPushView,
    MpesaCallbackView,
    StkQueryView,
    MpesaTransactionListView,
    StudentFeeBalanceView,
)

app_name = 'fees'

urlpatterns = [
    path('structures/', FeeStructureListCreateView.as_view(), name='fee-structure-list-create'),
    path('structures/<int:pk>/', FeeStructureDetailView.as_view(), name='fee-structure-detail'),
    path('payments/', FeePaymentListCreateView.as_view(), name='fee-payment-list-create'),
    path('payments/<int:pk>/', FeePaymentDetailView.as_view(), name='fee-payment-detail'),
    path('payments/student/<int:student_id>/', StudentPaymentsView.as_view(), name='student-payments'),
    path('balance/student/<int:student_id>/', StudentFeeBalanceView.as_view(), name='student-fee-balance'),
    path('mpesa/stk-push/', StkPushView.as_view(), name='mpesa-stk-push'),
    path('mpesa/callback/', MpesaCallbackView.as_view(), name='mpesa-callback'),
    path('mpesa/query/', StkQueryView.as_view(), name='mpesa-stk-query'),
    path('mpesa/transactions/', MpesaTransactionListView.as_view(), name='mpesa-transactions'),
]
