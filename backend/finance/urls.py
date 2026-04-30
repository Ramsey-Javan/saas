from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeeStructureViewSet, PaymentViewSet, MPesaTransactionViewSet

router = DefaultRouter()
router.register(r'fee-structures', FeeStructureViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'mpesa-transactions', MPesaTransactionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
