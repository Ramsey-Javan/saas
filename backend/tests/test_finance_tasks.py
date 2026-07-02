from datetime import timedelta

from django.utils.text import slugify
from django.utils import timezone

from finance.models import Payment
from finance.tasks import query_mpesa_status_task, reconcile_pending_mpesa_task
from students.models import Classroom, Student
from tenants.models import Tenant


def test_query_mpesa_status_task_returns_no_checkout_id(db):
    tenant = Tenant.objects.create(
        name='M-Pesa School',
        domain='http://mpesa-school.localhost',
        email='admin@mpesa-school.co.ke',
    )
    tenant.slug = slugify(tenant.name)
    tenant.save(update_fields=['slug'])
    classroom = Classroom.objects.create(tenant=tenant, name='Grade 4', grade_level='Grade 4', stream='Blue', academic_year='2026', capacity=40)
    student = Student.objects.create(
        tenant=tenant,
        classroom=classroom,
        admission_number='MPESA/0001',
        first_name='Test',
        last_name='Student',
        date_of_birth='2015-01-01',
        gender='M',
    )
    payment = Payment.objects.create(
        tenant=tenant,
        student=student,
        amount='1000.00',
        payment_method='mpesa',
        status='pending',
        mpesa_checkout_request_id='',
        idempotency_key='mpesa-task-no-checkout',
    )

    result = query_mpesa_status_task(payment.id)

    assert result == {'status': 'no_checkout_id'}


def test_reconcile_pending_mpesa_task_schedules_and_expires_stale_payments(db, monkeypatch):
    tenant = Tenant.objects.create(
        name='Reconcile School',
        domain='http://reconcile-school.localhost',
        email='admin@reconcile-school.co.ke',
    )
    tenant.slug = slugify(tenant.name)
    tenant.save(update_fields=['slug'])
    classroom = Classroom.objects.create(tenant=tenant, name='Grade 4', grade_level='Grade 4', stream='Blue', academic_year='2026', capacity=40)
    student = Student.objects.create(
        tenant=tenant,
        classroom=classroom,
        admission_number='RECON/0001',
        first_name='Test',
        last_name='Student',
        date_of_birth='2015-01-01',
        gender='M',
    )
    stale = Payment.objects.create(
        tenant=tenant,
        student=student,
        amount='1000.00',
        payment_method='mpesa',
        status='pending',
        mpesa_checkout_request_id='checkout-stale',
        idempotency_key='stale-payment',
    )
    ancient = Payment.objects.create(
        tenant=tenant,
        student=student,
        amount='1000.00',
        payment_method='mpesa',
        status='pending',
        mpesa_checkout_request_id='checkout-ancient',
        idempotency_key='ancient-payment',
    )
    recent = Payment.objects.create(
        tenant=tenant,
        student=student,
        amount='1000.00',
        payment_method='mpesa',
        status='pending',
        mpesa_checkout_request_id='checkout-recent',
        idempotency_key='recent-payment',
    )

    Payment.objects.filter(id=stale.id).update(created_at=timezone.now() - timedelta(minutes=1))
    Payment.objects.filter(id=ancient.id).update(created_at=timezone.now() - timedelta(minutes=11))
    Payment.objects.filter(id=recent.id).update(created_at=timezone.now() - timedelta(seconds=20))

    queued = []
    monkeypatch.setattr('finance.tasks.query_mpesa_status_task.delay', lambda payment_id: queued.append(payment_id))

    result = reconcile_pending_mpesa_task()

    stale.refresh_from_db()
    ancient.refresh_from_db()
    recent.refresh_from_db()

    assert queued == [stale.id, ancient.id]
    assert result['queried'] == 2
    assert result['expired'] == 1
    assert stale.status == 'pending'
    assert ancient.status == 'expired'
    assert recent.status == 'pending'
