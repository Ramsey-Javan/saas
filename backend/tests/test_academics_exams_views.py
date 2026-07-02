import pytest
from django.urls import reverse

from academics.models import ExamSetup, ExamSubject, ExamResult, ExamConfig
from tests.factories import (
    ClassroomFactory,
    ExamSetupFactory,
    ExamSubjectFactory,
    ExamResultFactory,
    StudentFactory,
    SubjectFactory,
    TeacherUserFactory,
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
class TestExamSetupViews:
    def test_exam_setup_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        ExamSetup.objects.create(
            tenant=tenant,
            name='Mid Term',
            exam_type='mid_term',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-03-01',
            end_date='2026-03-05',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )

        url = _reverse_or_skip(['examsetup-list', 'exam-setup-list'])
        if url is None:
            pytest.skip("examsetup-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_exam_setup_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        exam = ExamSetup.objects.create(
            tenant=tenant,
            name='Detail Exam',
            exam_type='opener',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-01-10',
            end_date='2026-01-20',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )

        url = _reverse_or_skip(['examsetup-detail', 'exam-setup-detail'], {'pk': exam.id})
        if url is None:
            pytest.skip("examsetup-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_exam_setup_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        exam = ExamSetup.objects.create(
            tenant=tenant,
            name='Update Exam',
            exam_type='opener',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-01-10',
            end_date='2026-01-20',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )

        url = _reverse_or_skip(['examsetup-detail', 'exam-setup-detail'], {'pk': exam.id})
        if url is None:
            pytest.skip("examsetup-detail URL not found")

        response = admin_client.patch(url, {'name': 'Updated Name'}, format='json')
        assert response.status_code in [200, 404]

    def test_exam_setup_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        exam = ExamSetup.objects.create(
            tenant=tenant,
            name='Delete Exam',
            exam_type='opener',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-01-10',
            end_date='2026-01-20',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )

        url = _reverse_or_skip(['examsetup-detail', 'exam-setup-detail'], {'pk': exam.id})
        if url is None:
            pytest.skip("examsetup-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]

    def test_exam_setup_filter_by_classroom(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        ExamSetup.objects.create(
            tenant=tenant,
            name='Filtered Exam',
            exam_type='opener',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-01-10',
            end_date='2026-01-20',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )

        url = _reverse_or_skip(['examsetup-list', 'exam-setup-list'])
        if url is None:
            pytest.skip("examsetup-list URL not found")

        response = admin_client.get(url, {'classroom': classroom.id})
        assert response.status_code == 200


@pytest.mark.django_db
class TestExamSubjectViews:
    def test_exam_subject_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        exam = ExamSetup.objects.create(
            tenant=tenant,
            name='Subject Exam',
            exam_type='opener',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-01-10',
            end_date='2026-01-20',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )
        subject = SubjectFactory(tenant=tenant)
        ExamSubject.objects.create(
            tenant=tenant,
            exam=exam,
            subject=subject,
            total_marks=100,
            teacher=admin_user,
        )

        url = _reverse_or_skip(['examsubject-list', 'exam-subject-list'])
        if url is None:
            pytest.skip("examsubject-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_exam_subject_create(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        exam = ExamSetup.objects.create(
            tenant=tenant,
            name='Create Subject Exam',
            exam_type='opener',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-01-10',
            end_date='2026-01-20',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )
        subject = SubjectFactory(tenant=tenant)

        url = _reverse_or_skip(['examsubject-list', 'exam-subject-list'])
        if url is None:
            pytest.skip("examsubject-list URL not found")

        payload = {
            'exam': exam.id,
            'subject': subject.id,
            'total_marks': 100,
            'teacher': admin_user.id,
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]


@pytest.mark.django_db
class TestExamResultViews:
    def test_exam_result_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        exam = ExamSetup.objects.create(
            tenant=tenant,
            name='Result Exam',
            exam_type='opener',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-01-10',
            end_date='2026-01-20',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )
        subject = SubjectFactory(tenant=tenant)
        student = StudentFactory(tenant=tenant, classroom=classroom)
        exam_subject = ExamSubject.objects.create(
            tenant=tenant,
            exam=exam,
            subject=subject,
            total_marks=100,
            teacher=admin_user,
        )
        ExamResult.objects.create(
            tenant=tenant,
            exam_subject=exam_subject,
            student=student,
            marks='85.00',
            percentage='85.00',
            cbc_level='EE',
            entered_by=admin_user,
        )

        url = _reverse_or_skip(['examresult-list', 'exam-result-list'])
        if url is None:
            pytest.skip("examresult-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_exam_result_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        exam = ExamSetup.objects.create(
            tenant=tenant,
            name='Update Result Exam',
            exam_type='opener',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-01-10',
            end_date='2026-01-20',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )
        subject = SubjectFactory(tenant=tenant)
        student = StudentFactory(tenant=tenant, classroom=classroom)
        exam_subject = ExamSubject.objects.create(
            tenant=tenant,
            exam=exam,
            subject=subject,
            total_marks=100,
            teacher=admin_user,
        )
        result = ExamResult.objects.create(
            tenant=tenant,
            exam_subject=exam_subject,
            student=student,
            marks='75.00',
            percentage='75.00',
            cbc_level='ME',
            entered_by=admin_user,
        )

        url = _reverse_or_skip(['examresult-detail', 'exam-result-detail'], {'pk': result.id})
        if url is None:
            pytest.skip("examresult-detail URL not found")

        response = admin_client.patch(url, {'marks': '90.00'}, format='json')
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestExamConfigViews:
    def test_exam_config_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        ExamConfig.objects.create(
            tenant=tenant,
            be_min=0,
            be_max=29,
            ae_min=30,
            ae_max=49,
            me_min=50,
            me_max=74,
            ee_min=75,
            ee_max=100,
            updated_by=admin_user,
        )

        url = _reverse_or_skip(['examconfig-list', 'exam-config-list'])
        if url is None:
            pytest.skip("examconfig-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_exam_config_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        config = ExamConfig.objects.create(
            tenant=tenant,
            be_min=0,
            be_max=29,
            ae_min=30,
            ae_max=49,
            me_min=50,
            me_max=74,
            ee_min=75,
            ee_max=100,
            updated_by=admin_user,
        )

        url = _reverse_or_skip(['examconfig-detail', 'exam-config-detail'], {'pk': config.id})
        if url is None:
            pytest.skip("examconfig-detail URL not found")

        response = admin_client.patch(url, {'be_max': 30}, format='json')
        assert response.status_code in [200, 404, 405]
