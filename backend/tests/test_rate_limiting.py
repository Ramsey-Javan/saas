import pytest


@pytest.mark.django_db
class TestPlanEnforcement:
    def test_login_throttled_after_too_many_attempts(self, anon_client, admin_user):
        # Try up to 20 times to hit the rate limit
        throttled = False
        for i in range(20):
            response = anon_client.post('/api/auth/token/', {
                'email': admin_user.email,
                'password': 'wrong-password',
            }, format='json')
            if response.status_code == 429:
                throttled = True
                break
            # Early attempts should be 401 (unauthorized)
            assert response.status_code in (401, 400)

        assert throttled, "Expected to be rate limited but wasn't"
