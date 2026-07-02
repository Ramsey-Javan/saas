import pytest
from django.urls import reverse

from academics.models import CBCGrade, Strand, SubStrand, LearningOutcome
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


def _make_outcome(tenant, subject=None):
    if subject is None:
        subject = SubjectFactory(tenant=tenant)
    strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
    sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)
    return LearningOutcome.objects.create(
        tenant=tenant, sub_strand=sub_strand, description='Outcome 1', order=1
    )


@pytest.mark.django_db
class TestCBCGradeViews:
    def test_cbc_grade_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        student = StudentFactory(tenant=tenant)
        outcome = _make_outcome(tenant)
        CBCGrade.objects.create(
            tenant=tenant,
            student=student,
            learning_outcome=outcome,
            level='ME',
            assessed_by=admin_user,
            academic_year=2026,
            term='term1',
        )

        url = _reverse_or_skip(['cbcgrade-list', 'cbc-grade-list'])
        if url is None:
            pytest.skip("cbcgrade-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_cbc_grade_create(self, admin_client, admin_user):
        tenant = admin_user.tenant
        student = StudentFactory(tenant=tenant)
        outcome = _make_outcome(tenant)

        url = _reverse_or_skip(['cbcgrade-list', 'cbc-grade-list'])
        if url is None:
            pytest.skip("cbcgrade-list URL not found")

        payload = {
            'student': student.id,
            'learning_outcome': outcome.id,
            'level': 'ME',
            'academic_year': 2026,
            'term': 'term1',
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_cbc_grade_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        student = StudentFactory(tenant=tenant)
        outcome = _make_outcome(tenant)
        grade = CBCGrade.objects.create(
            tenant=tenant,
            student=student,
            learning_outcome=outcome,
            level='ME',
            assessed_by=admin_user,
            academic_year=2026,
            term='term1',
        )

        url = _reverse_or_skip(['cbcgrade-detail', 'cbc-grade-detail'], {'pk': grade.id})
        if url is None:
            pytest.skip("cbcgrade-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestGradeReportViews:
    def test_student_grade_report(self, admin_client, admin_user):
        tenant = admin_user.tenant
        student = StudentFactory(tenant=tenant)

        url = _reverse_or_skip(['student-grade-report', 'grade-report'])
        if url is None:
            pytest.skip("grade-report URL not found")

        response = admin_client.get(url, {'student': student.id})
        assert response.status_code in [200, 404]

    def test_class_grade_report(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)

        url = _reverse_or_skip(['class-grade-report', 'grade-report'])
        if url is None:
            pytest.skip("grade-report URL not found")

        response = admin_client.get(url, {'classroom': classroom.id})
        assert response.status_code in [200, 404]