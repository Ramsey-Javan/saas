from rest_framework import serializers
from .models import FeeStructure, Payment, MPesaTransaction


class FeeStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'


class MPesaTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MPesaTransaction
        fields = '__all__'
