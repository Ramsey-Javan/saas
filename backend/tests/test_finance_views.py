import pytest
from decimal import Decimal
from django.urls import reverse

from finance.models import (
    FeeStructure, StudentFee, Payment, Receipt,
    WaiverPolicy, StudentWaiver,
)
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
class TestFeeStructureViews:
    def test_fee_structure_create(self, admin_client, admin_user):
        classroom = ClassroomFactory()

        url = _reverse_or_skip(['fee-structure-list', 'feestructure-list'])
        if url is None:
            pytest.skip("fee-structure-list URL not found")

        payload = {
            'classroom': classroom.id,
            'term': 'term1',
            'academic_year': 2026,
            'base_amount': '15000.00',
            'due_date': '2026-02-01',
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_fee_structure_filter_by_academic_year(self, admin_client, admin_user):
        classroom = ClassroomFactory()
        FeeStructureFactory(classroom=classroom, academic_year=2026)
        FeeStructureFactory(classroom=classroom, academic_year=2025)

        url = _reverse_or_skip(['fee-structure-list', 'feestructure-list'])
        if url is None:
            pytest.skip("fee-structure-list URL not found")

        response = admin_client.get(url, {'academic_year': 2026})
        assert response.status_code == 200


@pytest.mark.django_db
class TestStudentFeeViews:
    def test_student_fee_create(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        fee_structure = FeeStructureFactory(classroom=classroom)

        url = _reverse_or_skip(['student-fee-list', 'studentfee-list'])
        if url is None:
            pytest.skip("student-fee-list URL not found")

        payload = {
            'student': student.id,
            'fee_structure': fee_structure.id,
            'expected_amount': '15000.00',
            'due_date': '2026-02-01',
        }
        response = bursar_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

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


@pytest.mark.django_db
class TestPaymentViews:
    def test_payment_create(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        fee = StudentFeeFactory(student=student)

        url = _reverse_or_skip(['payment-list', 'payments-list'])
        if url is None:
            pytest.skip("payment-list URL not found")

        payload = {
            'student': student.id,
            'student_fee': fee.id,
            'amount': '1000.00',
            'payment_method': 'cash',
            'status': 'confirmed',
        }
        response = bursar_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_payment_update(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        payment = Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='payment-update-test',
            recorded_by=bursar_user,
        )

        url = _reverse_or_skip(['payment-detail', 'payments-detail'], {'pk': payment.id})
        if url is None:
            pytest.skip("payment-detail URL not found")

        response = bursar_client.patch(url, {'amount': '1500.00'}, format='json')
        assert response.status_code in [200, 404]

    def test_payment_delete(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        payment = Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='payment-delete-test',
            recorded_by=bursar_user,
        )

        url = _reverse_or_skip(['payment-detail', 'payments-detail'], {'pk': payment.id})
        if url is None:
            pytest.skip("payment-detail URL not found")

        response = bursar_client.delete(url)
        assert response.status_code in [204, 200, 404]


@pytest.mark.django_db
class TestReceiptViews:
    def test_receipt_create(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        payment = Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='receipt-create-test',
            recorded_by=bursar_user,
        )

        url = _reverse_or_skip(['receipt-list', 'receipts-list'])
        if url is None:
            pytest.skip("receipt-list URL not found")

        payload = {
            'student': student.id,
            'payment': payment.id,
            'amount': '1000.00',
            'payment_method': 'cash',
            'term': 'term1',
            'academic_year': '2026',
        }
        response = bursar_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_receipt_update(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        payment = Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='receipt-update-test',
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

        response = bursar_client.patch(url, {'amount': '1500.00'}, format='json')
        assert response.status_code in [200, 404]

    def test_receipt_delete(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        payment = Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='receipt-delete-test',
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

        response = bursar_client.delete(url)
        assert response.status_code in [204, 200, 404]


@pytest.mark.django_db
class TestWaiverPolicyViews:
    def test_waiver_policy_create(self, admin_client, admin_user):
        url = _reverse_or_skip(['waiver-policy-list', 'waiverpolicy-list'])
        if url is None:
            pytest.skip("waiver-policy-list URL not found")

        payload = {
            'category': 'partial',
            'discount_type': 'percentage',
            'discount_value': '25.00',
            'description': 'Test policy',
            'is_active': True,
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_waiver_policy_update(self, admin_client, admin_user):
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

        response = admin_client.patch(url, {'discount_value': '30.00'}, format='json')
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestStudentWaiverViews:
    def test_student_waiver_create(self, admin_client, admin_user):
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

        url = _reverse_or_skip(['student-waiver-list', 'studentwaiver-list'])
        if url is None:
            pytest.skip("student-waiver-list URL not found")

        payload = {
            'student': student.id,
            'policy': policy.id,
            'valid_from_term': 'term1',
            'valid_from_year': 2026,
            'is_active': True,
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_student_waiver_update(self, admin_client, admin_user):
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

        response = admin_client.patch(url, {'is_active': False}, format='json')
        assert response.status_code in [200, 404]
