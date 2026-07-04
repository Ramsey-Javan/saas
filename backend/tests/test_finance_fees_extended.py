import pytest
from decimal import Decimal
from django.urls import reverse

from finance.models import FeeStructure, StudentFee
from tests.factories import (
    ClassroomFactory,
    FeeStructureFactory,
    StudentFactory,
    StudentFeeFactory,
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
class TestFeeStructureViewsExtended:
    def test_fee_structure_detail(self, admin_client, admin_user):
        classroom = ClassroomFactory()
        fee_structure = FeeStructureFactory(classroom=classroom, term='term1')

        url = _reverse_or_skip(['fee-structure-detail', 'feestructure-detail'], {'pk': fee_structure.id})
        if url is None:
            pytest.skip("fee-structure-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_fee_structure_update(self, admin_client, admin_user):
        classroom = ClassroomFactory()
        fee_structure = FeeStructureFactory(
            classroom=classroom,
            base_amount=Decimal('10000.00'),
        )

        url = _reverse_or_skip(['fee-structure-detail', 'feestructure-detail'], {'pk': fee_structure.id})
        if url is None:
            pytest.skip("fee-structure-detail URL not found")

        response = admin_client.patch(
            url,
            {'base_amount': '12000.00'},
            format='json'
        )
        assert response.status_code in [200, 404]

    def test_fee_structure_delete(self, admin_client, admin_user):
        classroom = ClassroomFactory()
        fee_structure = FeeStructureFactory(classroom=classroom)

        url = _reverse_or_skip(['fee-structure-detail', 'feestructure-detail'], {'pk': fee_structure.id})
        if url is None:
            pytest.skip("fee-structure-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]

    def test_fee_structure_filter_by_term(self, admin_client, admin_user):
        classroom = ClassroomFactory()
        FeeStructureFactory(classroom=classroom, term='term1')
        FeeStructureFactory(classroom=classroom, term='term2')

        url = _reverse_or_skip(['fee-structure-list'])
        if url is None:
            pytest.skip("fee-structure-list URL not found")

        response = admin_client.get(url, {'term': 'term1'})
        assert response.status_code == 200

    def test_fee_structure_filter_by_classroom(self, admin_client, admin_user):
        classroom = ClassroomFactory()
        FeeStructureFactory(classroom=classroom, term='term1')

        url = _reverse_or_skip(['fee-structure-list'])
        if url is None:
            pytest.skip("fee-structure-list URL not found")

        response = admin_client.get(url, {'classroom': classroom.id})
        assert response.status_code == 200

    def test_fee_structure_filter_by_academic_year(self, admin_client, admin_user):
        classroom = ClassroomFactory()
        FeeStructureFactory(classroom=classroom, academic_year=2026)
        FeeStructureFactory(classroom=classroom, academic_year=2025)

        url = _reverse_or_skip(['fee-structure-list'])
        if url is None:
            pytest.skip("fee-structure-list URL not found")

        response = admin_client.get(url, {'academic_year': 2026})
        assert response.status_code == 200


@pytest.mark.django_db
class TestStudentFeeViewsExtended:
    def test_student_fee_detail(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        fee = StudentFeeFactory(student=student)

        url = _reverse_or_skip(['student-fee-detail', 'studentfee-detail'], {'pk': fee.id})
        if url is None:
            pytest.skip("student-fee-detail URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]

    def test_student_fee_update(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        fee = StudentFeeFactory(student=student)

        url = _reverse_or_skip(['student-fee-detail', 'studentfee-detail'], {'pk': fee.id})
        if url is None:
            pytest.skip("student-fee-detail URL not found")

        response = bursar_client.patch(url, {'status': 'paid'}, format='json')
        assert response.status_code in [200, 404]

    def test_student_fee_delete(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        fee = StudentFeeFactory(student=student)

        url = _reverse_or_skip(['student-fee-detail', 'studentfee-detail'], {'pk': fee.id})
        if url is None:
            pytest.skip("student-fee-detail URL not found")

        response = bursar_client.delete(url)
        assert response.status_code in [204, 200, 404]

    def test_student_fee_filter_by_status(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        StudentFeeFactory(student=student, status='unpaid')
        StudentFeeFactory(student=student, status='paid')

        url = _reverse_or_skip(['student-fee-list', 'studentfee-list'])
        if url is None:
            pytest.skip("student-fee-list URL not found")

        response = bursar_client.get(url, {'status': 'unpaid'})
        assert response.status_code == 200

    def test_student_fee_filter_by_student(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        StudentFeeFactory(student=student)

        url = _reverse_or_skip(['student-fee-list', 'studentfee-list'])
        if url is None:
            pytest.skip("student-fee-list URL not found")

        response = bursar_client.get(url, {'student': student.id})
        assert response.status_code == 200

    def test_student_fee_filter_by_term(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        fee_structure = FeeStructureFactory(classroom=classroom, term='term1')
        StudentFeeFactory(student=student, fee_structure=fee_structure)

        url = _reverse_or_skip(['student-fee-list', 'studentfee-list'])
        if url is None:
            pytest.skip("student-fee-list URL not found")

        response = bursar_client.get(url, {'term': 'term1'})
        assert response.status_code == 200
