from rest_framework import serializers
from .models import Client, Domain


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['id', 'domain', 'is_primary']


class ClientSerializer(serializers.ModelSerializer):
    domains = DomainSerializer(many=True, read_only=True)

    class Meta:
        model = Client
        fields = [
            'id', 'name', 'school_name', 'schema_name', 'created_on',
            'is_active', 'subscription_plan', 'subscription_expires_on',
            'contact_email', 'contact_phone', 'domains',
        ]
        read_only_fields = ['schema_name', 'created_on']


class ClientCreateSerializer(serializers.ModelSerializer):
    domain = serializers.CharField(write_only=True, help_text='Primary domain for the tenant')

    class Meta:
        model = Client
        fields = [
            'name', 'school_name', 'schema_name', 'contact_email',
            'contact_phone', 'subscription_plan', 'domain',
        ]

    def validate_schema_name(self, value):
        if not value.isidentifier():
            raise serializers.ValidationError(
                'Schema name must be a valid identifier (letters, numbers, underscores).'
            )
        return value.lower()

    def create(self, validated_data):
        domain_name = validated_data.pop('domain')
        client = Client.objects.create(**validated_data)
        Domain.objects.create(domain=domain_name, tenant=client, is_primary=True)
        return client
