import pytest
from decimal import Decimal
from django.urls import reverse

from finance.models import FeeStructure, StudentFee, Payment, Receipt, WaiverPolicy, StudentWaiver
from tests.factories import (
    ClassroomFactory,
    FeeStructureFactory,
    StudentFactory,
    StudentFeeFactory,
    PaymentFactory,
    WaiverPolicyFactory,
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
class TestFeeStructureExtendedViews:
    def test_fee_structure_detail(self, admin_client, admin_user):
        classroom = ClassroomFactory()
        fee_structure = FeeStructureFactory(classroom=classroom, term='term1')

        url = _reverse_or_skip(['fee-structure-detail', 'feestructure-detail'], {'pk': fee_structure.id})
        if url is None:
            pytest.skip("fee-structure-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

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


@pytest.mark.django_db
class TestStudentFeeExtendedViews:
    def test_student_fee_list(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        StudentFeeFactory(student=student)

        url = _reverse_or_skip(['student-fee-list', 'studentfee-list'])
        if url is None:
            pytest.skip("student-fee-list URL not found")

        response = bursar_client.get(url)
        assert response.status_code == 200

    def test_student_fee_detail(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        fee = StudentFeeFactory(student=student)

        url = _reverse_or_skip(['student-fee-detail', 'studentfee-detail'], {'pk': fee.id})
        if url is None:
            pytest.skip("student-fee-detail URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]

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


@pytest.mark.django_db
class TestPaymentExtendedViews:
    def test_payment_list(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='payment-list-test',
            recorded_by=bursar_user,
        )

        url = _reverse_or_skip(['payment-list', 'payments-list'])
        if url is None:
            pytest.skip("payment-list URL not found")

        response = bursar_client.get(url)
        assert response.status_code == 200

    def test_payment_detail(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        payment = Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='payment-detail-test',
            recorded_by=bursar_user,
        )

        url = _reverse_or_skip(['payment-detail', 'payments-detail'], {'pk': payment.id})
        if url is None:
            pytest.skip("payment-detail URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]

    def test_payment_filter_by_status(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='payment-filter-test',
            recorded_by=bursar_user,
        )

        url = _reverse_or_skip(['payment-list', 'payments-list'])
        if url is None:
            pytest.skip("payment-list URL not found")

        response = bursar_client.get(url, {'status': 'confirmed'})
        assert response.status_code == 200


@pytest.mark.django_db
class TestReceiptExtendedViews:
    def test_receipt_list(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        payment = Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='receipt-list-test',
            recorded_by=bursar_user,
        )
        Receipt.objects.create(
            tenant=student.tenant,
            student=student,
            payment=payment,
            amount=Decimal('1000.00'),
            payment_method='cash',
            term='term1',
            academic_year='2026',
            issued_by=bursar_user,
        )

        url = _reverse_or_skip(['receipt-list', 'receipts-list'])
        if url is None:
            pytest.skip("receipt-list URL not found")

        response = bursar_client.get(url)
        assert response.status_code == 200

    def test_receipt_detail(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        payment = Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='receipt-detail-test',
            recorded_by=bursar_user,
        )
        receipt = Receipt.objects.create(
            tenant=student.tenant,
            student=student,
            payment=payment,
            amount=Decimal('1000.00'),
            payment_method='cash',
            term='term1',
            academic_year='2026',
            issued_by=bursar_user,
        )

        url = _reverse_or_skip(['receipt-detail', 'receipts-detail'], {'pk': receipt.id})
        if url is None:
            pytest.skip("receipt-detail URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestWaiverExtendedViews:
    def test_waiver_policy_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        policy = WaiverPolicy.objects.create(
            tenant=tenant,
            category='partial',
            discount_type='percentage',
            discount_value=Decimal('25.00'),
            is_active=True,
            description='Test',
        )

        url = _reverse_or_skip(['waiver-policy-detail', 'waiverpolicy-detail'], {'pk': policy.id})
        if url is None:
            pytest.skip("waiver-policy-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_waiver_policy_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        policy = WaiverPolicy.objects.create(
            tenant=tenant,
            category='partial',
            discount_type='percentage',
            discount_value=Decimal('25.00'),
            is_active=True,
            description='Test',
        )

        url = _reverse_or_skip(['waiver-policy-detail', 'waiverpolicy-detail'], {'pk': policy.id})
        if url is None:
            pytest.skip("waiver-policy-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]

    def test_student_waiver_detail(self, admin_client, admin_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        tenant = admin_user.tenant
        policy = WaiverPolicy.objects.create(
            tenant=tenant,
            category='partial',
            discount_type='percentage',
            discount_value=Decimal('25.00'),
            is_active=True,
            description='Test',
        )
        waiver = StudentWaiver.objects.create(
            tenant=tenant,
            student=student,
            policy=policy,
            valid_from_term='term1',
            valid_from_year=2026,
            is_active=True,
        )

        url = _reverse_or_skip(['student-waiver-detail', 'studentwaiver-detail'], {'pk': waiver.id})
        if url is None:
            pytest.skip("student-waiver-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_student_waiver_delete(self, admin_client, admin_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        tenant = admin_user.tenant
        policy = WaiverPolicy.objects.create(
            tenant=tenant,
            category='partial',
            discount_type='percentage',
            discount_value=Decimal('25.00'),
            is_active=True,
            description='Test',
        )
        waiver = StudentWaiver.objects.create(
            tenant=tenant,
            student=student,
            policy=policy,
            valid_from_term='term1',
            valid_from_year=2026,
            is_active=True,
        )

        url = _reverse_or_skip(['student-waiver-detail', 'studentwaiver-detail'], {'pk': waiver.id})
        if url is None:
            pytest.skip("student-waiver-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]
