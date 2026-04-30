from django.urls import path
from .views import TenantListCreateView, TenantDetailView, CurrentTenantView, TenantActivationView

app_name = 'tenants'

urlpatterns = [
    path('', TenantListCreateView.as_view(), name='tenant-list-create'),
    path('<str:schema_name>/', TenantDetailView.as_view(), name='tenant-detail'),
    path('<str:schema_name>/activation/', TenantActivationView.as_view(), name='tenant-activation'),
    path('current/', CurrentTenantView.as_view(), name='current-tenant'),
]
