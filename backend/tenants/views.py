from rest_framework import viewsets
from .models import Tenant
from .serializers import TenantSerializer


class TenantViewSet(viewsets.ModelViewSet):
    """ViewSet for Tenant management."""
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
