from decimal import Decimal

from finance.utils import (
    calculate_waived_amount,
    get_carry_forward,
    get_sibling_discount,
    recalculate_student_fees,
)
from finance.models import FeeStructure, Payment, StudentFee, StudentWaiver, WaiverPolicy
from students.models import Guardian, Student
from tests.factories import (
    ClassroomFactory,
    FeeStructureFactory,
    GuardianFactory,
    StudentFactory,
    StudentFeeFactory,
    TenantFactory,
)


def test_get_carry_forward_uses_previous_term_balance(db):
    tenant = TenantFactory()
    classroom = ClassroomFactory(tenant=tenant)
    student = StudentFactory(tenant=tenant, classroom=classroom)
    previous = FeeStructureFactory(tenant=tenant, classroom=student.classroom, term='term1', academic_year=2026)
    current = FeeStructureFactory(tenant=tenant, classroom=student.classroom, term='term2', academic_year=2026)
    previous_invoice = StudentFeeFactory(
        tenant=tenant,
        student=student,
        fee_structure=previous,
        expected_amount=Decimal('1000.00'),
        due_date=previous.due_date,
    )
    Payment.objects.create(
        tenant=tenant,
        student=student,
        student_fee=previous_invoice,
        amount=Decimal('400.00'),
        payment_method='cash',
        status='confirmed',
        idempotency_key='carry-forward-test',
        recorded_by=student.user,
    )

    carry_forward = get_carry_forward(student, current.term, current.academic_year)

    assert carry_forward == Decimal('600.00')


def test_calculate_waived_amount_returns_matching_waiver(db):
    tenant = TenantFactory()
    classroom = ClassroomFactory(tenant=tenant)
    student = StudentFactory(tenant=tenant, classroom=classroom)
    policy = WaiverPolicy.objects.create(
        tenant=tenant,
        category='partial',
        discount_type='percentage',
        discount_value=Decimal('25.00'),
        is_active=True,
        description='Test waiver',
        created_by=None,
    )
    waiver = StudentWaiver.objects.create(
        tenant=tenant,
        student=student,
        policy=policy,
        approved_by=None,
        valid_from_term='term1',
        valid_from_year=2026,
        valid_until_term='term2',
        valid_until_year=2026,
        is_active=True,
    )

    waived_amount, matched_waiver = calculate_waived_amount(
        student,
        Decimal('1200.00'),
        'term2',
        2026,
    )

    assert waived_amount == Decimal('300.00')
    assert matched_waiver == waiver


def test_recalculate_student_fees_cascades_credit_forward(db):
    tenant = TenantFactory()
    classroom = ClassroomFactory(tenant=tenant)
    student = StudentFactory(tenant=tenant, classroom=classroom)
    term1 = FeeStructureFactory(tenant=tenant, classroom=student.classroom, term='term1', academic_year=2026)
    term2 = FeeStructureFactory(tenant=tenant, classroom=student.classroom, term='term2', academic_year=2026)
    first_invoice = StudentFeeFactory(
        tenant=tenant,
        student=student,
        fee_structure=term1,
        expected_amount=Decimal('1000.00'),
        due_date=term1.due_date,
    )
    second_invoice = StudentFeeFactory(
        tenant=tenant,
        student=student,
        fee_structure=term2,
        expected_amount=Decimal('1000.00'),
        due_date=term2.due_date,
    )
    Payment.objects.create(
        tenant=tenant,
        student=student,
        student_fee=first_invoice,
        amount=Decimal('1500.00'),
        payment_method='cash',
        status='confirmed',
        idempotency_key='recalc-credit-test',
        recorded_by=student.user,
    )

    recalculate_student_fees(student)

    first_invoice.refresh_from_db()
    second_invoice.refresh_from_db()

    # The credit may be applied to next invoice rather than stored on first
    # Check that the overall accounting is correct
    assert first_invoice.paid_amount == Decimal('1000.00')
    assert first_invoice.status == 'paid'
    # Credit may be on first invoice or already cascaded to second
    total_credit = first_invoice.credit + second_invoice.credit
    total_paid_second = second_invoice.paid_amount
    assert total_credit + total_paid_second == Decimal('500.00')
    # Second invoice should have been partially paid from the credit
    assert second_invoice.paid_amount > Decimal('0.00') or second_invoice.credit > Decimal('0.00')


def test_get_sibling_discount_uses_active_policy(db):
    tenant = TenantFactory()
    guardian = GuardianFactory()
    classroom = ClassroomFactory(tenant=tenant)
    student = StudentFactory(tenant=tenant, classroom=classroom, primary_guardian=guardian)
    StudentFactory(tenant=tenant, classroom=classroom, primary_guardian=guardian)
    policy = WaiverPolicy.objects.create(
        tenant=tenant,
        category='sibling',
        discount_type='fixed',
        discount_value=Decimal('2000.00'),
        is_active=True,
        description='Sibling discount',
        created_by=None,
    )

    discount_policy = get_sibling_discount(student)

    assert discount_policy == policy
