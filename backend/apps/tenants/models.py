from django_tenants.models import TenantMixin, DomainMixin
from django.db import models


class Client(TenantMixin):
    name = models.CharField(max_length=100)
    school_name = models.CharField(max_length=200)
    created_on = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    subscription_plan = models.CharField(
        max_length=20,
        choices=[('free', 'Free'), ('basic', 'Basic'), ('premium', 'Premium')],
        default='free',
    )
    subscription_expires_on = models.DateField(null=True, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=15, blank=True)

    auto_create_schema = True

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['schema_name']

    def __str__(self):
        return f'{self.school_name} ({self.schema_name})'


class Domain(DomainMixin):
    class Meta:
        verbose_name = 'Domain'
        verbose_name_plural = 'Domains'

    def __str__(self):
        return self.domain
