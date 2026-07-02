from decimal import Decimal

from django.urls import reverse

from finance.models import Payment, Receipt, StudentFee
from tests.factories import ClassroomFactory, FeeStructureFactory, PaymentFactory, StudentFactory, StudentFeeFactory


def test_manual_cash_payment_creates_receipt_and_updates_invoice(bursar_client, bursar_user, db, monkeypatch):
    classroom = ClassroomFactory(tenant=bursar_user.tenant)
    student = StudentFactory(tenant=bursar_user.tenant, classroom=classroom)
    fee_structure = FeeStructureFactory(tenant=student.tenant, classroom=student.classroom, term='term1', academic_year=2026)
    invoice = StudentFeeFactory(
        tenant=student.tenant,
        student=student,
        fee_structure=fee_structure,
        expected_amount=Decimal('1500.00'),
        due_date=fee_structure.due_date,
    )
    monkeypatch.setattr('finance.utils.recalculate_student_fees', lambda student: None)
    monkeypatch.setattr('finance.views.payments._send_payment_sms', lambda *args, **kwargs: None)

    response = bursar_client.post(
        reverse('payment-manual'),
        {
            'invoice_id': str(invoice.id),
            'amount': '1500.00',
            'method': 'cash',
            'send_sms': False,
        },
        format='json',
    )

    invoice.refresh_from_db()

    assert response.status_code == 201
    assert response.data['payment']['status'] == 'confirmed'
    assert response.data['receipt_number']
    assert invoice.status == 'paid'
    assert Receipt.objects.filter(payment__student=student).count() == 1


def test_clear_cheque_marks_payment_confirmed(bursar_client, bursar_user, db, monkeypatch):
    student = StudentFactory(tenant=bursar_user.tenant, classroom=ClassroomFactory(tenant=bursar_user.tenant))
    fee_structure = FeeStructureFactory(tenant=student.tenant, classroom=student.classroom, term='term1', academic_year=2026)
    invoice = StudentFeeFactory(
        tenant=student.tenant,
        student=student,
        fee_structure=fee_structure,
        expected_amount=Decimal('500.00'),
        due_date=fee_structure.due_date,
    )
    payment = Payment.objects.create(
        tenant=student.tenant,
        student=student,
        student_fee=invoice,
        amount=Decimal('500.00'),
        payment_method='cheque',
        status='pending',
        idempotency_key='clear-cheque-test',
        recorded_by=bursar_user,
    )
    monkeypatch.setattr('finance.utils.recalculate_student_fees', lambda student: None)
    monkeypatch.setattr('finance.views.payments._send_payment_sms', lambda *args, **kwargs: None)

    response = bursar_client.patch(
        reverse('payment-clear-cheque', kwargs={'pk': payment.id}),
        {},
        format='json',
    )

    payment.refresh_from_db()

    assert response.status_code == 200
    assert payment.status == 'confirmed'
    assert response.data['receipt_number']
    assert response.data['payment']['status'] == 'confirmed'


def test_bounce_cheque_requires_reason_and_marks_bounced(bursar_client, bursar_user, db, monkeypatch):
    student = StudentFactory(tenant=bursar_user.tenant, classroom=ClassroomFactory(tenant=bursar_user.tenant))
    fee_structure = FeeStructureFactory(tenant=student.tenant, classroom=student.classroom, term='term1', academic_year=2026)
    invoice = StudentFeeFactory(
        tenant=student.tenant,
        student=student,
        fee_structure=fee_structure,
        expected_amount=Decimal('500.00'),
        due_date=fee_structure.due_date,
    )
    payment = Payment.objects.create(
        tenant=student.tenant,
        student=student,
        student_fee=invoice,
        amount=Decimal('500.00'),
        payment_method='cheque',
        status='confirmed',
        idempotency_key='bounce-cheque-test',
        recorded_by=bursar_user,
    )
    monkeypatch.setattr('finance.utils.recalculate_student_fees', lambda student: None)
    monkeypatch.setattr('finance.views.payments.send_sms_task.delay', lambda *args, **kwargs: None)

    response = bursar_client.patch(
        reverse('payment-bounce-cheque', kwargs={'pk': payment.id}),
        {'reason': 'Cheque bounced by bank'},
        format='json',
    )

    payment.refresh_from_db()

    assert response.status_code == 200
    assert payment.status == 'bounced'
    assert payment.notes == 'Cheque bounced by bank'
    assert response.data['payment']['status'] == 'bounced'


def test_stk_push_returns_checkout_request_id(bursar_client, bursar_user, db, monkeypatch):
    classroom = ClassroomFactory(tenant=bursar_user.tenant)
    student = StudentFactory(tenant=bursar_user.tenant, classroom=classroom)
    invoice = StudentFeeFactory(tenant=student.tenant, student=student)
    monkeypatch.setattr(
        'finance.views.payments.MpesaService.initiate_stk_push',
        lambda self, **kwargs: {
            'ResponseCode': '0',
            'CheckoutRequestID': 'ws_CO_test_123',
            'CustomerMessage': 'Success',
        },
    )

    response = bursar_client.post(
        reverse('mpesa-stk-push'),
        {
            'student': student.id,
            'student_fee': str(invoice.id),
            'amount': '1000.00',
            'phone': '0712345678',
            'account_ref': student.admission_number,
        },
        format='json',
    )

    assert response.status_code == 201
    assert response.data['success'] is True
    assert response.data['checkout_request_id'] == 'ws_CO_test_123'
    assert Payment.objects.filter(student=student, payment_method='mpesa', status='pending').exists()


def test_callback_returns_processed_result(bursar_client, db, monkeypatch):
    monkeypatch.setattr(
        'finance.views.payments.MpesaService.process_callback',
        lambda self, data: {'status': 'processed', 'checkout_request_id': data['Body']['stkCallback']['CheckoutRequestID']},
    )

    response = bursar_client.post(
        reverse('mpesa-callback'),
        {'Body': {'stkCallback': {'CheckoutRequestID': 'ws_CO_test_123'}}},
        format='json',
    )

    assert response.status_code == 200
    assert response.data['status'] == 'processed'
