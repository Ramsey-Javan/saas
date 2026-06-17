"""Base abstract model for academics app."""
from django.db import models

from tenants.models import Tenant


class TenantModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    class Meta:
        abstract = True
        app_label = 'academics'
