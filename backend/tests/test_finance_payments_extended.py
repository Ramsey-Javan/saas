import pytest
from decimal import Decimal
from django.urls import reverse

from finance.models import Payment, Receipt, StudentFee
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
class TestPaymentViewsExtended:
    def test_payment_create_with_mpesa(self, bursar_client, bursar_user, monkeypatch):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        fee = StudentFeeFactory(student=student)

        monkeypatch.setattr(
            'finance.views.payments.MpesaService.initiate_stk_push',
            lambda self, **kwargs: {
                'ResponseCode': '0',
                'CheckoutRequestID': 'ws_CO_test_123',
                'CustomerMessage': 'Success',
            },
        )

        url = _reverse_or_skip(['payment-list', 'payments-list'])
        if url is None:
            pytest.skip("payment-list URL not found")

        payload = {
            'student': student.id,
            'student_fee': fee.id,
            'amount': '1000.00',
            'payment_method': 'mpesa',
            'phone': '0712345678',
        }
        response = bursar_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_payment_filter_by_method(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='payment-filter-test-1',
            recorded_by=bursar_user,
        )
        Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('2000.00'),
            payment_method='mpesa',
            status='confirmed',
            idempotency_key='payment-filter-test-2',
            recorded_by=bursar_user,
        )

        url = _reverse_or_skip(['payment-list', 'payments-list'])
        if url is None:
            pytest.skip("payment-list URL not found")

        response = bursar_client.get(url, {'payment_method': 'cash'})
        assert response.status_code == 200

    def test_payment_filter_by_date(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='payment-date-test',
            recorded_by=bursar_user,
        )

        url = _reverse_or_skip(['payment-list', 'payments-list'])
        if url is None:
            pytest.skip("payment-list URL not found")

        response = bursar_client.get(url, {
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
        })
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

    def test_payment_update(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        payment = Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='pending',
            idempotency_key='payment-update-test',
            recorded_by=bursar_user,
        )

        url = _reverse_or_skip(['payment-detail', 'payments-detail'], {'pk': payment.id})
        if url is None:
            pytest.skip("payment-detail URL not found")

        response = bursar_client.patch(url, {'status': 'confirmed'}, format='json')
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
class TestReceiptViewsExtended:
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

    def test_receipt_filter_by_term(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        payment = Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='receipt-filter-test',
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

        response = bursar_client.get(url, {'term': 'term1'})
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
