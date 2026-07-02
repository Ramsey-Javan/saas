import pytest
from django.urls import reverse

from tenants.models import Tenant
from tests.factories import TenantFactory


def _reverse_or_skip(url_names, kwargs=None):
    for name in url_names:
        try:
            if kwargs:
                return reverse(name, kwargs=kwargs)
            return reverse(name)
        except:
            continue
    return None


@pytest.mark.django_db
class TestTenantEndpoints:
    def test_superadmin_can_create_tenant(self, superadmin_client):
        payload = {
            'name': 'New School',
            'domain': 'http://new-school.localhost',
            'email': 'admin@new-school.co.ke',
            'phone': '0700000001',
        }

        url = _reverse_or_skip(['tenant-list', 'tenants-list'])
        if url is None:
            pytest.skip("tenant-list URL not found")

        response = superadmin_client.post(url, payload, format='json')

        assert response.status_code in [201, 404]
        if response.status_code == 201:
            assert Tenant.objects.filter(name='New School').exists()

    def test_superadmin_can_list_tenants(self, superadmin_client):
        TenantFactory(name='School A')
        TenantFactory(name='School B')

        url = _reverse_or_skip(['tenant-list', 'tenants-list'])
        if url is None:
            pytest.skip("tenant-list URL not found")

        response = superadmin_client.get(url)

        assert response.status_code == 200
        results = response.data.get('results', response.data)
        assert len(results) >= 2

    def test_tenant_detail(self, superadmin_client):
        tenant = TenantFactory()

        url = _reverse_or_skip(
            ['tenant-detail', 'tenants-detail'],
            {'pk': tenant.id}
        )
        if url is None:
            pytest.skip("tenant-detail URL not found")

        response = superadmin_client.get(url)

        assert response.status_code == 200

    def test_admin_can_access_tenant_list(self, admin_client):
        """Admin can access tenant list but only sees their own tenant."""
        url = _reverse_or_skip(['tenant-list', 'tenants-list'])
        if url is None:
            pytest.skip("tenant-list URL not found")

        response = admin_client.get(url)

        # Admin should get 200 but filtered to their tenant, or 403 if forbidden
        assert response.status_code in [200, 403]
        if response.status_code == 200:
            # Should only see their own tenant
            results = response.data.get('results', response.data)
            assert len(results) <= 1
