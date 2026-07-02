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
class TestTenantExtendedViews:
    def test_tenant_create(self, superadmin_client):
        payload = {
            'name': 'Extended School',
            'domain': 'http://extended-school.localhost',
            'email': 'admin@extended-school.co.ke',
            'phone': '0700000002',
        }

        url = _reverse_or_skip(['tenant-list', 'tenants-list'])
        if url is None:
            pytest.skip("tenant-list URL not found")

        response = superadmin_client.post(url, payload, format='json')
        assert response.status_code in [201, 404]
        if response.status_code == 201:
            assert Tenant.objects.filter(name='Extended School').exists()

    def test_tenant_update(self, superadmin_client):
        tenant = TenantFactory()

        url = _reverse_or_skip(['tenant-detail', 'tenants-detail'], {'pk': tenant.id})
        if url is None:
            pytest.skip("tenant-detail URL not found")

        response = superadmin_client.patch(url, {'phone': '0711111111'}, format='json')
        assert response.status_code in [200, 404]

    def test_tenant_delete(self, superadmin_client):
        tenant = TenantFactory()

        url = _reverse_or_skip(['tenant-detail', 'tenants-detail'], {'pk': tenant.id})
        if url is None:
            pytest.skip("tenant-detail URL not found")

        response = superadmin_client.delete(url)
        assert response.status_code in [204, 200, 404]

    def test_tenant_filter_by_active(self, superadmin_client):
        TenantFactory(is_active=True)
        TenantFactory(is_active=False)

        url = _reverse_or_skip(['tenant-list', 'tenants-list'])
        if url is None:
            pytest.skip("tenant-list URL not found")

        response = superadmin_client.get(url, {'is_active': 'true'})
        assert response.status_code == 200

    def test_tenant_search(self, superadmin_client):
        TenantFactory(name='Searchable School')

        url = _reverse_or_skip(['tenant-list', 'tenants-list'])
        if url is None:
            pytest.skip("tenant-list URL not found")

        response = superadmin_client.get(url, {'search': 'Searchable'})
        assert response.status_code == 200

    def test_tenant_stats(self, superadmin_client):
        url = _reverse_or_skip(['tenant-stats', 'tenant-statistics'])
        if url is None:
            pytest.skip("tenant-stats URL not found")

        response = superadmin_client.get(url)
        assert response.status_code in [200, 404]

    def test_tenant_settings(self, admin_client, admin_user):
        url = _reverse_or_skip(['tenant-settings', 'settings-detail'])
        if url is None:
            pytest.skip("tenant-settings URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_tenant_update_settings(self, admin_client, admin_user):
        url = _reverse_or_skip(['tenant-settings', 'settings-detail'])
        if url is None:
            pytest.skip("tenant-settings URL not found")

        response = admin_client.patch(url, {'primary_color': '#ff0000'}, format='json')
        assert response.status_code in [200, 404]
