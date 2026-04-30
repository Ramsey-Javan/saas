from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django_tenants.utils import get_tenant_model
from .models import Client, Domain
from .serializers import ClientSerializer, ClientCreateSerializer


class TenantListCreateView(generics.ListCreateAPIView):
    queryset = Client.objects.all()
    permission_classes = [permissions.IsAdminUser]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ClientCreateSerializer
        return ClientSerializer


class TenantDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = 'schema_name'


class CurrentTenantView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=ClientSerializer)
    def get(self, request):
        tenant = request.tenant
        serializer = ClientSerializer(tenant)
        return Response(serializer.data)


class TenantActivationView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['activate', 'deactivate']}}}},
        responses={200: OpenApiResponse(description='Success message')},
    )
    def post(self, request, schema_name):
        try:
            tenant = Client.objects.get(schema_name=schema_name)
        except Client.DoesNotExist:
            return Response({'detail': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        if action == 'activate':
            tenant.is_active = True
        elif action == 'deactivate':
            tenant.is_active = False
        else:
            return Response({'detail': 'Invalid action. Use activate or deactivate.'}, status=status.HTTP_400_BAD_REQUEST)

        tenant.save(update_fields=['is_active'])
        return Response({'detail': f'Tenant {action}d successfully.'})
