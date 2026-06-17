"""Shared mixins, helpers, and inline serializers for finance views."""
import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import (
    Case,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from students.models import Student

from ..models import CONFIRMED_PAYMENT_STATUSES, Payment, Receipt, StudentFee
from ..permissions import IsAdminOrBursar
from ..utils import apply_waiver_to_invoices, remove_waiver_from_invoices
from communication.models import SMSLog
from communication.sms import send_sms_task


class STKPushSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    student_fee = serializers.PrimaryKeyRelatedField(
        queryset=StudentFee.objects.all(),
        required=False,
        allow_null=True,
    )
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('1.00'))
    phone = serializers.RegexField(regex=r'^(?:254|\+254|0)?[17]\d{8}$')
    account_ref = serializers.CharField(required=False, allow_blank=True, max_length=50)
    description = serializers.CharField(required=False, allow_blank=True, max_length=100)


class ManualPaymentSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('1.00'))
    method = serializers.ChoiceField(choices=['cash', 'bank', 'cheque'])
    date = serializers.DateField(required=False, allow_null=True)
    bank_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    bank_reference = serializers.CharField(required=False, allow_blank=True, max_length=100)
    cheque_number = serializers.CharField(required=False, allow_blank=True, max_length=50)
    drawer_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    notes = serializers.CharField(required=False, allow_blank=True)
    send_sms = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        method = attrs.get('method')
        if method == 'bank':
            if not attrs.get('bank_name'):
                raise serializers.ValidationError({'bank_name': 'Bank name is required for bank transfers.'})
            if not attrs.get('bank_reference'):
                raise serializers.ValidationError({'bank_reference': 'Bank reference is required for bank transfers.'})
        if method == 'cheque':
            if not attrs.get('cheque_number'):
                raise serializers.ValidationError({'cheque_number': 'Cheque number is required for cheque payments.'})
            if not attrs.get('bank_name'):
                raise serializers.ValidationError({'bank_name': 'Bank name is required for cheque payments.'})
            if not attrs.get('drawer_name'):
                raise serializers.ValidationError({'drawer_name': 'Drawer name is required for cheque payments.'})
        return attrs


class TenantScopedMixin:
    """Scope every finance query and create to the authenticated user's school."""

    permission_classes = [IsAdminOrBursar]

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = getattr(self.request.user, 'tenant', None)
        if tenant:
            return queryset.filter(tenant=tenant)
        if getattr(self.request.user, 'is_superuser', False):
            return queryset
        return queryset.none()

    def perform_create(self, serializer):
        tenant = getattr(self.request.user, 'tenant', None)
        if not tenant and not getattr(self.request.user, 'is_superuser', False):
            raise PermissionDenied('Finance records must be created under a school tenant.')
        serializer.save(tenant=tenant)


def outstanding_expression(paid_field='paid_total'):
    """
    Per-invoice outstanding balance for THIS row only, including its own
    cascaded carried_forward. Safe to use in .filter()/.annotate() when
    inspecting ONE invoice at a time (e.g. defaulters list). NEVER sum this
    across multiple invoices belonging to the same student/class/tenant --
    see gross_due_expression() below for why.
    """
    return ExpressionWrapper(
        F('expected_amount')
        + F('carried_forward')
        + F('penalty_amount')
        - F('waived_amount')
        - F(paid_field),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def total_due_expression():
    """
    Per-invoice total obligation for THIS row only (own fee + cascaded
    carried_forward + penalty - waived). Safe for single-row use (e.g.
    displaying one invoice's own balance). NEVER sum this across multiple
    invoices -- carried_forward is a snapshot of prior terms' OWN
    expected_amount/penalty/waived, so summing total_due across a student's
    terms counts the same arrears 2x, 3x, etc. Use gross_due_expression()
    for any cross-invoice aggregation (dashboards, class/term summaries).
    """
    return ExpressionWrapper(
        F('expected_amount') + F('carried_forward') + F('penalty_amount') - F('waived_amount'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def gross_due_expression():
    """
    The TRUE per-invoice fee obligation, EXCLUDING carried_forward.

    THIS is the expression to use whenever SUMMING across multiple invoices --
    e.g. dashboard "Total Expected", class reports, term summaries spanning
    many students/terms. carried_forward is just a cascaded snapshot of prior
    terms' own expected_amount/penalty/waived -- it is NOT new debt, and is
    already accounted for via those prior terms' own gross_due. Summing
    total_due_expression() (which embeds carried_forward) across multiple
    invoices double/triple counts the same arrears every time they roll
    forward into a new term.

    Safe to Sum() across any number of invoices/students/terms.
    """
    return ExpressionWrapper(
        F('expected_amount') + F('penalty_amount') - F('waived_amount'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def _confirmed_payment_filter():
    return Q(payments__status__in=CONFIRMED_PAYMENT_STATUSES)


def _recalculate_invoice(invoice):
    if not invoice:
        return None
    
    from ..utils import recalculate_student_fees  # local import to avoid circularity
    
    money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
    total_paid = (
        Payment.objects.filter(student_fee=invoice, status__in=CONFIRMED_PAYMENT_STATUSES)
        .aggregate(total=Coalesce(Sum('amount'), money_zero))
        .get('total')
        or Decimal('0.00')
    )
    total_due = max(
        Decimal('0.00'),
        invoice.expected_amount + invoice.carried_forward + invoice.penalty_amount - invoice.waived_amount,
    )
    invoice.paid_amount = min(total_paid, total_due)
    invoice.credit = max(Decimal('0.00'), total_paid - total_due)
    if invoice.paid_amount >= total_due:
        status_value = 'paid'
    elif invoice.paid_amount > 0:
        status_value = 'partial'
    else:
        status_value = 'unpaid'
    invoice.status = status_value
    invoice.save(update_fields=['paid_amount', 'credit', 'status', 'updated_at'])
    
    # CRITICAL: Cascade recalculation to all of this student's invoices
    recalculate_student_fees(invoice.student)
    
    return invoice


def _create_receipt_for_payment(payment):
    try:
        return payment.receipt
    except Receipt.DoesNotExist:
        pass

    fee = payment.student_fee
    return Receipt.objects.create(
        tenant=payment.tenant,
        student=payment.student,
        payment=payment,
        amount=payment.amount,
        payment_method=payment.payment_method,
        term=fee.fee_structure.term if fee else '',
        academic_year=fee.fee_structure.academic_year if fee else '',
        issued_by=payment.recorded_by,
    )


def _send_payment_sms(student, amount, receipt_number, remaining_balance):
    guardian = getattr(student, 'primary_guardian', None)
    if not guardian or not guardian.phone:
        return None
    message = (
        f"Dear {guardian.full_name}, payment of KES {amount:,.2f} received "
        f"for {student.get_full_name()} ({student.admission_number}). "
        f"Receipt: {receipt_number}. "
        f"Balance: KES {remaining_balance:,.2f}."
    )
    log = SMSLog.objects.create(
        tenant=student.tenant,
        recipient_phone=guardian.phone,
        message=message,
        status='pending',
        provider='africas_talking',
        reference_id=None,
    )
    send_sms_task.delay([guardian.phone], message, log.id)
    return log