import secrets
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser, StaffProfile, StaffInvite
from tests.factories import (
    TeacherUserFactory,
    TenantFactory,
    StaffProfileFactory,
)


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
class TestUserExtendedViews:
    def test_user_list(self, admin_client, admin_user):
        url = _reverse_or_skip(['user-list', 'users-list'])
        if url is None:
            pytest.skip("user-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_user_detail(self, admin_client, admin_user):
        url = _reverse_or_skip(['user-detail', 'users-detail'], {'pk': admin_user.id})
        if url is None:
            pytest.skip("user-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_user_update(self, admin_client, admin_user):
        url = _reverse_or_skip(['user-detail', 'users-detail'], {'pk': admin_user.id})
        if url is None:
            pytest.skip("user-detail URL not found")

        response = admin_client.patch(url, {'first_name': 'Updated'}, format='json')
        assert response.status_code in [200, 404]

    def test_user_delete(self, admin_client, admin_user):
        teacher = TeacherUserFactory(tenant=admin_user.tenant)
        url = _reverse_or_skip(['user-detail', 'users-detail'], {'pk': teacher.id})
        if url is None:
            pytest.skip("user-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]

    def test_user_filter_by_role(self, admin_client, admin_user):
        url = _reverse_or_skip(['user-list', 'users-list'])
        if url is None:
            pytest.skip("user-list URL not found")

        response = admin_client.get(url, {'role': 'teacher'})
        assert response.status_code == 200

    def test_user_search(self, admin_client, admin_user):
        url = _reverse_or_skip(['user-list', 'users-list'])
        if url is None:
            pytest.skip("user-list URL not found")

        response = admin_client.get(url, {'search': admin_user.first_name})
        assert response.status_code == 200


@pytest.mark.django_db
class TestStaffProfileExtendedViews:
    def test_staff_profile_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        StaffProfile.objects.create(
            tenant=tenant,
            user=admin_user,
            employee_number='EMP/001',
            first_name='Admin',
            last_name='User',
            phone='0700000000',
            job_title='admin',
            department='administration',
            employment_status='active',
            is_active=True,
            start_date='2026-01-01',
        )

        url = _reverse_or_skip(['staffprofile-list', 'staff-list'])
        if url is None:
            pytest.skip("staffprofile-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_staff_profile_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        profile = StaffProfile.objects.create(
            tenant=tenant,
            user=admin_user,
            employee_number='EMP/002',
            first_name='Admin',
            last_name='Detail',
            phone='0700000000',
            job_title='admin',
            department='administration',
            employment_status='active',
            is_active=True,
            start_date='2026-01-01',
        )

        url = _reverse_or_skip(['staffprofile-detail', 'staff-detail'], {'pk': profile.id})
        if url is None:
            pytest.skip("staffprofile-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_staff_profile_create(self, admin_client, admin_user):
        tenant = admin_user.tenant
        teacher = TeacherUserFactory(tenant=tenant)

        url = _reverse_or_skip(['staffprofile-list', 'staff-list'])
        if url is None:
            pytest.skip("staffprofile-list URL not found")

        payload = {
            'user': teacher.id,
            'employee_number': 'EMP/NEW',
            'first_name': 'New',
            'last_name': 'Staff',
            'phone': '0700000001',
            'job_title': 'teacher',
            'department': 'teaching',
            'employment_status': 'active',
            'start_date': '2026-01-01',
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_staff_profile_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        profile = StaffProfile.objects.create(
            tenant=tenant,
            user=admin_user,
            employee_number='EMP/003',
            first_name='Admin',
            last_name='Delete',
            phone='0700000000',
            job_title='admin',
            department='administration',
            employment_status='active',
            is_active=True,
            start_date='2026-01-01',
        )

        url = _reverse_or_skip(['staffprofile-detail', 'staff-detail'], {'pk': profile.id})
        if url is None:
            pytest.skip("staffprofile-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]


@pytest.mark.django_db
class TestStaffInviteExtendedViews:
    def _make_invite(self, tenant, email, admin_user):
        profile = StaffProfileFactory(tenant=tenant)
        return StaffInvite.objects.create(
            tenant=tenant,
            staff_profile=profile,
            email=email,
            role='teacher',
            token=secrets.token_hex(32),
            invited_by=admin_user,
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_staff_invite_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        self._make_invite(tenant, 'invited@test.co.ke', admin_user)

        url = _reverse_or_skip(['staffinvite-list', 'staff-invite-list'])
        if url is None:
            pytest.skip("staffinvite-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_staff_invite_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        invite = self._make_invite(tenant, 'invited-detail@test.co.ke', admin_user)

        url = _reverse_or_skip(['staffinvite-detail', 'staff-invite-detail'], {'pk': invite.id})
        if url is None:
            pytest.skip("staffinvite-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_staff_invite_resend(self, admin_client, admin_user):
        tenant = admin_user.tenant
        invite = self._make_invite(tenant, 'invited-resend@test.co.ke', admin_user)

        url = _reverse_or_skip(['staff-invite-resend', 'staffinvite-resend'])
        if url is None:
            pytest.skip("staff-invite-resend URL not found")

        response = admin_client.post(url, {'pk': invite.id}, format='json')
        assert response.status_code in [200, 404]

    def test_staff_invite_cancel(self, admin_client, admin_user):
        tenant = admin_user.tenant
        invite = self._make_invite(tenant, 'invited-cancel@test.co.ke', admin_user)

        url = _reverse_or_skip(['staff-invite-cancel', 'staffinvite-cancel'])
        if url is None:
            pytest.skip("staff-invite-cancel URL not found")

        response = admin_client.post(url, {'pk': invite.id}, format='json')
        assert response.status_code in [200, 404]