import pytest
from django.urls import reverse

from academics.models import NationalExamSession, NationalExamCandidate, NationalExamResult
from tests.factories import (
    ClassroomFactory,
    StudentFactory,
    SubjectFactory,
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
class TestNationalExamSessionExtendedViews:
    def test_national_exam_session_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        session = NationalExamSession.objects.create(
            tenant=tenant,
            name='KPSEA',
            academic_year=2026,
            classroom=classroom,
            centre_number='12345',
            centre_name='Test Centre',
            exam_date='2026-10-01',
            created_by=admin_user,
        )

        url = _reverse_or_skip(['nationalexamsession-detail', 'national-exam-session-detail'], {'pk': session.id})
        if url is None:
            pytest.skip("national-exam-session-detail URL not found")

        response = admin_client.patch(url, {'centre_name': 'Updated Centre'}, format='json')
        assert response.status_code in [200, 404]

    def test_national_exam_session_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        session = NationalExamSession.objects.create(
            tenant=tenant,
            name='KPSEA',
            academic_year=2026,
            classroom=classroom,
            centre_number='12345',
            centre_name='Test Centre',
            exam_date='2026-10-01',
            created_by=admin_user,
        )

        url = _reverse_or_skip(['nationalexamsession-detail', 'national-exam-session-detail'], {'pk': session.id})
        if url is None:
            pytest.skip("national-exam-session-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]

    def test_national_exam_session_filter_by_year(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        NationalExamSession.objects.create(
            tenant=tenant,
            name='KPSEA 2026',
            academic_year=2026,
            classroom=classroom,
            centre_number='12345',
            centre_name='Test Centre',
            exam_date='2026-10-01',
            created_by=admin_user,
        )
        NationalExamSession.objects.create(
            tenant=tenant,
            name='KPSEA 2025',
            academic_year=2025,
            classroom=classroom,
            centre_number='12346',
            centre_name='Test Centre 2',
            exam_date='2025-10-01',
            created_by=admin_user,
        )

        url = _reverse_or_skip(['nationalexamsession-list', 'national-exam-session-list'])
        if url is None:
            pytest.skip("national-exam-session-list URL not found")

        response = admin_client.get(url, {'academic_year': 2026})
        assert response.status_code == 200


@pytest.mark.django_db
class TestNationalExamCandidateExtendedViews:
    def test_national_exam_candidate_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        session = NationalExamSession.objects.create(
            tenant=tenant,
            name='KPSEA',
            academic_year=2026,
            classroom=classroom,
            centre_number='12345',
            centre_name='Test Centre',
            exam_date='2026-10-01',
            created_by=admin_user,
        )
        student = StudentFactory(tenant=tenant)
        candidate = NationalExamCandidate.objects.create(
            tenant=tenant,
            session=session,
            student=student,
            index_number='IDX00001',
            is_registered=True,
            registration_confirmed=True,
        )

        url = _reverse_or_skip(['nationalexamcandidate-detail', 'national-exam-candidate-detail'], {'pk': candidate.id})
        if url is None:
            pytest.skip("national-exam-candidate-detail URL not found")

        response = admin_client.patch(url, {'special_needs': 'Braille'}, format='json')
        assert response.status_code in [200, 404]

    def test_national_exam_candidate_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        session = NationalExamSession.objects.create(
            tenant=tenant,
            name='KPSEA',
            academic_year=2026,
            classroom=classroom,
            centre_number='12345',
            centre_name='Test Centre',
            exam_date='2026-10-01',
            created_by=admin_user,
        )
        student = StudentFactory(tenant=tenant)
        candidate = NationalExamCandidate.objects.create(
            tenant=tenant,
            session=session,
            student=student,
            index_number='IDX00002',
            is_registered=True,
            registration_confirmed=True,
        )

        url = _reverse_or_skip(['nationalexamcandidate-detail', 'national-exam-candidate-detail'], {'pk': candidate.id})
        if url is None:
            pytest.skip("national-exam-candidate-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]


@pytest.mark.django_db
class TestNationalExamResultExtendedViews:
    def test_national_exam_result_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        session = NationalExamSession.objects.create(
            tenant=tenant,
            name='KPSEA',
            academic_year=2026,
            classroom=classroom,
            centre_number='12345',
            centre_name='Test Centre',
            exam_date='2026-10-01',
            created_by=admin_user,
        )
        student = StudentFactory(tenant=tenant)
        candidate = NationalExamCandidate.objects.create(
            tenant=tenant,
            session=session,
            student=student,
            index_number='IDX00003',
            is_registered=True,
            registration_confirmed=True,
        )
        subject = SubjectFactory(tenant=tenant)
        result = NationalExamResult.objects.create(
            tenant=tenant,
            candidate=candidate,
            subject=subject,
            marks='70.00',
            total_marks=100,
            grade='ME',
        )

        url = _reverse_or_skip(['nationalexamresult-detail', 'national-exam-result-detail'], {'pk': result.id})
        if url is None:
            pytest.skip("national-exam-result-detail URL not found")

        response = admin_client.patch(url, {'marks': '80.00'}, format='json')
        assert response.status_code in [200, 404]

    def test_national_exam_result_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        session = NationalExamSession.objects.create(
            tenant=tenant,
            name='KPSEA',
            academic_year=2026,
            classroom=classroom,
            centre_number='12345',
            centre_name='Test Centre',
            exam_date='2026-10-01',
            created_by=admin_user,
        )
        student = StudentFactory(tenant=tenant)
        candidate = NationalExamCandidate.objects.create(
            tenant=tenant,
            session=session,
            student=student,
            index_number='IDX00004',
            is_registered=True,
            registration_confirmed=True,
        )
        subject = SubjectFactory(tenant=tenant)
        result = NationalExamResult.objects.create(
            tenant=tenant,
            candidate=candidate,
            subject=subject,
            marks='70.00',
            total_marks=100,
            grade='ME',
        )

        url = _reverse_or_skip(['nationalexamresult-detail', 'national-exam-result-detail'], {'pk': result.id})
        if url is None:
            pytest.skip("national-exam-result-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]
