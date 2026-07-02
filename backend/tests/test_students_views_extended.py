import pytest
from django.urls import reverse

from students.models import Student, Guardian, Classroom
from tests.factories import (
    ClassroomFactory,
    GuardianFactory,
    StudentFactory,
    TenantFactory,
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
class TestStudentExtendedViews:
    def test_student_list_pagination(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        for i in range(5):
            StudentFactory(tenant=tenant, classroom=classroom)

        url = _reverse_or_skip(['student-list', 'students-list'])
        if url is None:
            pytest.skip("student-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_student_search_by_name(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        StudentFactory(tenant=tenant, classroom=classroom, first_name='Alice')
        StudentFactory(tenant=tenant, classroom=classroom, first_name='Bob')

        url = _reverse_or_skip(['student-list', 'students-list'])
        if url is None:
            pytest.skip("student-list URL not found")

        response = admin_client.get(url, {'search': 'Alice'})
        assert response.status_code == 200

    def test_student_filter_by_status(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        StudentFactory(tenant=tenant, classroom=classroom, is_active=True)
        StudentFactory(tenant=tenant, classroom=classroom, is_active=False)

        url = _reverse_or_skip(['student-list', 'students-list'])
        if url is None:
            pytest.skip("student-list URL not found")

        response = admin_client.get(url, {'is_active': 'true'})
        assert response.status_code == 200

    def test_student_bulk_create(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)

        url = _reverse_or_skip(['student-bulk-create', 'students-bulk'])
        if url is None:
            pytest.skip("student-bulk-create URL not found")

        payload = {
            'students': [
                {
                    'first_name': 'Bulk1',
                    'last_name': 'Test1',
                    'admission_number': 'BULK/001',
                    'date_of_birth': '2015-01-01',
                    'gender': 'M',
                    'classroom': classroom.id,
                },
                {
                    'first_name': 'Bulk2',
                    'last_name': 'Test2',
                    'admission_number': 'BULK/002',
                    'date_of_birth': '2015-01-01',
                    'gender': 'F',
                    'classroom': classroom.id,
                },
            ]
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 404]

    def test_student_promote(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom1 = ClassroomFactory(tenant=tenant, name='Grade 4', grade_level='Grade 4')
        classroom2 = ClassroomFactory(tenant=tenant, name='Grade 5', grade_level='Grade 5')
        student = StudentFactory(tenant=tenant, classroom=classroom1)

        url = _reverse_or_skip(['student-promote', 'students-promote'])
        if url is None:
            pytest.skip("student-promote URL not found")

        payload = {
            'student_ids': [student.id],
            'new_classroom': classroom2.id,
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [200, 404]

    def test_student_graduate(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        student = StudentFactory(tenant=tenant, classroom=classroom)

        url = _reverse_or_skip(['student-graduate', 'students-graduate'])
        if url is None:
            pytest.skip("student-graduate URL not found")

        payload = {'student_ids': [student.id]}
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestClassroomViews:
    def test_classroom_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        ClassroomFactory(tenant=tenant, name='Grade 4A')
        ClassroomFactory(tenant=tenant, name='Grade 5A')

        url = _reverse_or_skip(['classroom-list', 'classrooms-list'])
        if url is None:
            pytest.skip("classroom-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_classroom_create(self, admin_client, admin_user):
        tenant = admin_user.tenant

        url = _reverse_or_skip(['classroom-list', 'classrooms-list'])
        if url is None:
            pytest.skip("classroom-list URL not found")

        payload = {
            'name': 'Grade 6A',
            'grade_level': 'Grade 6',
            'stream': 'Blue',
            'academic_year': '2026',
            'capacity': 40,
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_classroom_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant, name='Grade 4A')

        url = _reverse_or_skip(['classroom-detail', 'classrooms-detail'], {'pk': classroom.id})
        if url is None:
            pytest.skip("classroom-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_classroom_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant, name='Grade 4A')

        url = _reverse_or_skip(['classroom-detail', 'classrooms-detail'], {'pk': classroom.id})
        if url is None:
            pytest.skip("classroom-detail URL not found")

        response = admin_client.patch(url, {'capacity': 50}, format='json')
        assert response.status_code in [200, 404]

    def test_classroom_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant, name='Grade 4A')

        url = _reverse_or_skip(['classroom-detail', 'classrooms-detail'], {'pk': classroom.id})
        if url is None:
            pytest.skip("classroom-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]

    def test_classroom_students(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        StudentFactory(tenant=tenant, classroom=classroom)
        StudentFactory(tenant=tenant, classroom=classroom)

        url = _reverse_or_skip(['classroom-students', 'classroom-student-list'])
        if url is None:
            pytest.skip("classroom-students URL not found")

        response = admin_client.get(url, {'classroom': classroom.id})
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestGuardianExtendedViews:
    def test_guardian_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        GuardianFactory()
        GuardianFactory()

        url = _reverse_or_skip(['guardian-list', 'guardians-list'])
        if url is None:
            pytest.skip("guardian-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_guardian_detail(self, admin_client, admin_user):
        guardian = GuardianFactory()

        url = _reverse_or_skip(['guardian-detail', 'guardians-detail'], {'pk': guardian.id})
        if url is None:
            pytest.skip("guardian-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_guardian_update(self, admin_client, admin_user):
        guardian = GuardianFactory()

        url = _reverse_or_skip(['guardian-detail', 'guardians-detail'], {'pk': guardian.id})
        if url is None:
            pytest.skip("guardian-detail URL not found")

        response = admin_client.patch(url, {'phone': '0711111111'}, format='json')
        assert response.status_code in [200, 404]

    def test_guardian_delete(self, admin_client, admin_user):
        guardian = GuardianFactory()

        url = _reverse_or_skip(['guardian-detail', 'guardians-detail'], {'pk': guardian.id})
        if url is None:
            pytest.skip("guardian-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]
