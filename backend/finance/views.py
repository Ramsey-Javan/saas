from rest_framework import viewsets
from .models import FeeStructure, Payment, MPesaTransaction
from .serializers import FeeStructureSerializer, PaymentSerializer, MPesaTransactionSerializer


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


class MPesaTransactionViewSet(viewsets.ModelViewSet):
    queryset = MPesaTransaction.objects.all()
    serializer_class = MPesaTransactionSerializer
