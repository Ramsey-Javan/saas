import pytest
from rest_framework.test import APIClient

from tests.factories import (
    AdminUserFactory,
    BursarUserFactory,
    ClassroomFactory,
    StudentFactory,
    SuperAdminUserFactory,
    TeacherUserFactory,
    TenantFactory,
)


@pytest.fixture
def tenant(db):
    return TenantFactory()


@pytest.fixture
def other_tenant(db):
    return TenantFactory()


@pytest.fixture
def admin_user(db, tenant):
    return AdminUserFactory(tenant=tenant)


@pytest.fixture
def teacher_user(db, tenant):
    return TeacherUserFactory(tenant=tenant)


@pytest.fixture
def bursar_user(db, tenant):
    return BursarUserFactory(tenant=tenant)


@pytest.fixture
def superadmin_user(db):
    return SuperAdminUserFactory()


@pytest.fixture
def classroom(db, tenant):
    return ClassroomFactory(tenant=tenant)


@pytest.fixture
def student(db, tenant, classroom):
    return StudentFactory(tenant=tenant, classroom=classroom)


def _authed_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_client(admin_user):
    return _authed_client(admin_user)


@pytest.fixture
def teacher_client(teacher_user):
    return _authed_client(teacher_user)


@pytest.fixture
def bursar_client(bursar_user):
    return _authed_client(bursar_user)


@pytest.fixture
def superadmin_client(superadmin_user):
    return _authed_client(superadmin_user)


@pytest.fixture
def anon_client():
    return APIClient()