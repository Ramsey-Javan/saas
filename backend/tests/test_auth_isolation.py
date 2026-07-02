import pytest

from tests.factories import StudentFactory


@pytest.mark.django_db
class TestAuthAndTenantIsolation:
    def test_login_returns_jwt_with_role(self, anon_client, admin_user):
        response = anon_client.post('/api/auth/token/', {
            'email': admin_user.email,
            'password': 'testpass123',
        }, format='json')

        assert response.status_code == 200
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert response.data['user']['role'] == 'admin'

    def test_admin_cannot_see_other_schools_students(self, admin_client, tenant, other_tenant, student):
        other_student = StudentFactory(tenant=other_tenant)

        response = admin_client.get('/api/students/')

        assert response.status_code == 200
        results = response.data['results']
        assert not any(item['admission_number'] == other_student.admission_number for item in results)

    def test_teacher_cannot_access_finance_endpoints(self, teacher_client):
        response = teacher_client.get('/api/finance/payments/')
        assert response.status_code == 403

    def test_inactive_school_blocks_login(self, tenant, admin_user, anon_client):
        tenant.is_active = False
        tenant.save(update_fields=['is_active'])

        response = anon_client.post('/api/auth/token/', {
            'email': admin_user.email,
            'password': 'testpass123',
        }, format='json')

        assert response.status_code == 400
        assert response.data['error'] is True
        assert 'no longer active' in response.data['message'].lower()

    def test_jwt_refresh_flow(self, anon_client, admin_user):
        login = anon_client.post('/api/auth/token/', {
            'email': admin_user.email,
            'password': 'testpass123',
        }, format='json')
        refresh = login.data['refresh']

        response = anon_client.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json')

        assert response.status_code == 200
        assert 'access' in response.data