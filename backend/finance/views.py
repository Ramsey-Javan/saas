import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Case, DecimalField, ExpressionWrapper, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .mpesa import MpesaService
from .models import CONFIRMED_PAYMENT_STATUSES, FeeStructure, Payment, Receipt, StudentFee, WaiverPolicy, StudentWaiver
from .serializers import (
    FeeStructureSerializer,
    PaymentSerializer,
    ReceiptSerializer,
    StudentFeeSerializer,
    WaiverPolicySerializer,
    StudentWaiverSerializer,
)
from .utils import apply_waiver_to_invoices, remove_waiver_from_invoices, get_carry_forward, calculate_waived_amount, get_sibling_discount
from .permissions import IsAdminOrBursar, IsAdminBursarOrOwnParent
from communication.models import SMSLog
from communication.sms import send_sms_task
from students.models import Classroom, Student


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
    return ExpressionWrapper(
        F('expected_amount')
        + F('carried_forward')
        + F('penalty_amount')
        - F('waived_amount')
        - F(paid_field),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def total_due_expression():
    return ExpressionWrapper(
        F('expected_amount') + F('carried_forward') + F('penalty_amount') - F('waived_amount'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


def _confirmed_payment_filter():
    return Q(payments__status__in=CONFIRMED_PAYMENT_STATUSES)


def _recalculate_invoice(invoice):
    if not invoice:
        return None
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


@api_view(['GET'])
@permission_classes([IsAdminBursarOrOwnParent])
def student_statement(request, student_id):
    tenant = getattr(request.user, 'tenant', None)
    student = Student.objects.select_related('classroom', 'primary_guardian').filter(id=student_id, tenant=tenant).first()
    if not student:
        return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

    permission = IsAdminBursarOrOwnParent()
    if not permission.has_object_permission(request, None, student):
        return Response({'error': 'Not allowed to access this statement.'}, status=status.HTTP_403_FORBIDDEN)

    money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
    invoices_qs = (
        StudentFee.objects.filter(student=student, tenant=tenant)
        .select_related('fee_structure', 'waiver', 'waiver__policy')
        .annotate(
            total_due=total_due_expression(),
            paid_total=Coalesce(
                Sum('payments__amount', filter=_confirmed_payment_filter()),
                money_zero,
            ),
        )
        .annotate(
            credit_amount=Case(
                When(paid_total__gt=F('total_due'), then=F('paid_total') - F('total_due')),
                default=money_zero,
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            balance_amount=Case(
                When(paid_total__gte=F('total_due'), then=money_zero),
                default=F('total_due') - F('paid_total'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by('-fee_structure__academic_year', 'fee_structure__term')
    )

    summary = invoices_qs.aggregate(
        total_billed=Coalesce(Sum('total_due'), money_zero),
        total_paid=Coalesce(Sum('paid_total'), money_zero),
        total_waived=Coalesce(Sum('waived_amount'), money_zero),
        carried_forward=Coalesce(Sum('carried_forward'), money_zero),
    )
    total_balance = max(Decimal('0.00'), summary['total_billed'] - summary['total_paid'])

    def _waiver_scope(waiver):
        if not waiver:
            return None
        if waiver.valid_until_year is None:
            return 'permanent'
        if waiver.valid_from_year == waiver.valid_until_year:
            if waiver.valid_from_term == waiver.valid_until_term:
                return 'termly'
            return 'yearly'
        return 'yearly'

    invoices = []
    for inv in invoices_qs:
        scope = _waiver_scope(inv.waiver)
        invoices.append({
            'id': str(inv.id),
            'term': inv.fee_structure.term,
            'academic_year': inv.fee_structure.academic_year,
            'amount_due': str(max(Decimal('0.00'), inv.total_due)),
            'amount_paid': str(min(inv.paid_total, max(Decimal('0.00'), inv.total_due))),
            'waived_amount': str(inv.waived_amount or Decimal('0.00')),
            'waiver_scope': scope,
            'waiver_label': scope.capitalize() if scope else None,
            'waiver_reason': inv.waiver_reason or '',
            'balance': str(inv.balance_amount),
            'credit': str(inv.credit_amount),
            'carried_forward': str(inv.carried_forward),
            'status': inv.status,
            'due_date': inv.due_date,
        })

    payments = [
        {
            'id': str(payment.id),
            'amount': str(payment.amount),
            'method': payment.payment_method,
            'receipt_number': getattr(getattr(payment, 'receipt', None), 'receipt_number', None),
            'mpesa_receipt_number': payment.mpesa_receipt_number,
            'date': payment.created_at,
            'term': getattr(getattr(payment, 'student_fee', None), 'fee_structure', None).term if payment.student_fee else None,
            'academic_year': getattr(getattr(payment, 'student_fee', None), 'fee_structure', None).academic_year if payment.student_fee else None,
            'recorded_by': payment.recorded_by.get_full_name() if payment.recorded_by else None,
        }
        for payment in Payment.objects.filter(student=student, tenant=tenant)
        .select_related('receipt', 'recorded_by', 'student_fee__fee_structure')
        .order_by('-created_at')
    ]

    classroom = student.classroom
    photo_url = request.build_absolute_uri(student.photo.url) if student.photo else None
    return Response({
        'student': {
            'id': student.id,
            'full_name': student.get_full_name(),
            'admission_number': student.admission_number,
            'classroom_name': str(classroom) if classroom else None,
            'photo': photo_url,
        },
        'summary': {
            'total_billed': str(summary['total_billed']),
            'total_paid': str(summary['total_paid']),
            'total_waived': str(summary['total_waived']),
            'carried_forward': str(summary['carried_forward']),
            'total_balance': str(total_balance),
        },
        'invoices': invoices,
        'payments': payments,
    })


def _build_statement(student, tenant, term=None, academic_year=None):
    money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
    invoices_qs = (
        StudentFee.objects.filter(student=student, tenant=tenant)
        .select_related('fee_structure', 'waiver', 'waiver__policy')
    )
    invoices_qs = invoices_qs.filter(fee_structure__term=term) if term else invoices_qs
    invoices_qs = invoices_qs.filter(fee_structure__academic_year=academic_year) if academic_year is not None else invoices_qs

    invoices_qs = (
        invoices_qs.annotate(
            total_due=total_due_expression(),
            paid_total=Coalesce(
                Sum('payments__amount', filter=_confirmed_payment_filter()),
                money_zero,
            ),
        )
        .annotate(
            credit_amount=Case(
                When(paid_total__gt=F('total_due'), then=F('paid_total') - F('total_due')),
                default=money_zero,
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            balance_amount=Case(
                When(paid_total__gte=F('total_due'), then=money_zero),
                default=F('total_due') - F('paid_total'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by('-fee_structure__academic_year', 'fee_structure__term')
    )

    summary = invoices_qs.aggregate(
        total_billed=Coalesce(Sum('total_due'), money_zero),
        total_paid=Coalesce(Sum('paid_total'), money_zero),
        total_waived=Coalesce(Sum('waived_amount'), money_zero),
        carried_forward=Coalesce(Sum('carried_forward'), money_zero),
    )
    balance_due = max(Decimal('0.00'), summary['total_billed'] - summary['total_paid'])

    payments_qs = Payment.objects.filter(student=student, tenant=tenant)
    if term:
        payments_qs = payments_qs.filter(student_fee__fee_structure__term=term)
    if academic_year is not None:
        payments_qs = payments_qs.filter(student_fee__fee_structure__academic_year=academic_year)

    return {
        'student': student,
        'summary': summary,
        'balance_due': balance_due,
        'invoices': list(invoices_qs),
        'payments': list(payments_qs.select_related('receipt').order_by('-created_at')),
    }


@api_view(['GET'])
@permission_classes([IsAdminBursarOrOwnParent])
def student_statement_pdf(request, student_id):
    tenant = getattr(request.user, 'tenant', None)
    student = Student.objects.select_related('classroom').filter(id=student_id, tenant=tenant).first()
    if not student:
        return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

    permission = IsAdminBursarOrOwnParent()
    if not permission.has_object_permission(request, None, student):
        return Response({'error': 'Not allowed to access this statement.'}, status=status.HTTP_403_FORBIDDEN)

    statement = _build_statement(student, tenant)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="student_statement.pdf"'

    pdf = canvas.Canvas(response, pagesize=A4)
    page_width, page_height = A4
    margin_x = 36
    margin_y = 36
    paybill = settings.MPESA.get('SHORTCODE', '')

    def draw_table(title, headers, rows, y_start):
        y = y_start
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(margin_x, y, title)
        y -= 14
        pdf.setFont('Helvetica-Bold', 8)
        x = margin_x
        for header, width in headers:
            pdf.drawString(x, y, header)
            x += width
        y -= 12
        pdf.setFont('Helvetica', 8)
        for row in rows:
            if y < 70:
                pdf.showPage()
                y = page_height - margin_y
                pdf.setFont('Helvetica-Bold', 10)
                pdf.drawString(margin_x, y, title)
                y -= 14
                pdf.setFont('Helvetica-Bold', 8)
                x = margin_x
                for header, width in headers:
                    pdf.drawString(x, y, header)
                    x += width
                y -= 12
                pdf.setFont('Helvetica', 8)
            x = margin_x
            for value, width in row:
                x += width
            y -= 12
        return y

    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(margin_x, page_height - margin_y, 'Student Statement')
    pdf.setFont('Helvetica', 9)
    pdf.drawString(margin_x, page_height - margin_y - 16, f"Student: {student.get_full_name()}")
    pdf.drawString(margin_x, page_height - margin_y - 30, f"Admission: {student.admission_number}")
    pdf.drawString(margin_x, page_height - margin_y - 44, f"Class: {student.classroom or '—'}")
    pdf.drawString(margin_x, page_height - margin_y - 58, f"M-Pesa Paybill: {paybill}")
    pdf.drawString(margin_x, page_height - margin_y - 72, f"Account: {student.admission_number}")

    y = page_height - margin_y - 96
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(margin_x, y, 'Summary')
    y -= 14
    pdf.setFont('Helvetica', 9)
    pdf.drawString(margin_x, y, f"Total billed: KES {statement['summary']['total_billed']:,.2f}")
    y -= 12
    pdf.drawString(margin_x, y, f"Total paid: KES {statement['summary']['total_paid']:,.2f}")
    y -= 12
    pdf.drawString(margin_x, y, f"Total waived: KES {statement['summary']['total_waived']:,.2f}")
    y -= 12
    pdf.drawString(margin_x, y, f"Carried forward: KES {statement['summary']['carried_forward']:,.2f}")
    y -= 12
    pdf.drawString(margin_x, y, f"Balance due: KES {statement['balance_due']:,.2f}")
    y -= 18

    invoice_rows = []
    for inv in statement['invoices']:
        invoice_rows.append([
            (str(inv.fee_structure.term), 60),
            (str(inv.fee_structure.academic_year), 50),
            (f"KES {inv.total_due:,.2f}", 80),
            (f"KES {inv.waived_amount:,.2f}", 80),
            (f"KES {inv.paid_total:,.2f}", 80),
            (f"KES {inv.balance_amount:,.2f}", 80),
            (str(inv.status), 60),
        ])

    y = draw_table(
        'Invoices',
        [('Term', 60), ('Year', 50), ('Billed', 80), ('Waived', 80), ('Paid', 80), ('Balance', 80), ('Status', 60)],
        invoice_rows,
        y,
    )

    payment_rows = []
    for payment in statement['payments']:
        receipt_number = getattr(getattr(payment, 'receipt', None), 'receipt_number', '—')
        payment_rows.append([
            (payment.created_at.date().isoformat(), 70),
            (f"KES {payment.amount:,.2f}", 80),
            (str(payment.payment_method), 60),
            (str(receipt_number or '—'), 90),
            (str(payment.mpesa_receipt_number or '—'), 90),
        ])

    draw_table(
        'Payments',
        [('Date', 70), ('Amount', 80), ('Method', 60), ('Receipt', 90), ('M-Pesa', 90)],
        payment_rows,
        y - 6,
    )

    pdf.showPage()
    pdf.save()
    return response


@api_view(['POST'])
@permission_classes([IsAdminOrBursar])
def bulk_statement_pdf(request):
    term = request.data.get('term')
    academic_year = request.data.get('academic_year')
    classroom_id = request.data.get('classroom')

    if not term or academic_year is None or not classroom_id:
        return Response({'error': 'term, academic_year, and classroom are required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        academic_year = int(academic_year)
    except (TypeError, ValueError):
        return Response({'error': 'academic_year must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        raise PermissionDenied('PDF generation must be under a school tenant.')

    students = Student.objects.filter(tenant=tenant, classroom_id=classroom_id).select_related('classroom')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="class_statements.pdf"'

    pdf = canvas.Canvas(response, pagesize=A4)
    page_width, page_height = A4
    margin_x = 36
    margin_y = 36
    paybill = settings.MPESA.get('SHORTCODE', '')

    def draw_table(title, headers, rows, y_start):
        y = y_start
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(margin_x, y, title)
        y -= 14
        pdf.setFont('Helvetica-Bold', 8)
        x = margin_x
        for header, width in headers:
            pdf.drawString(x, y, header)
            x += width
        y -= 12
        pdf.setFont('Helvetica', 8)
        for row in rows:
            if y < 70:
                pdf.showPage()
                y = page_height - margin_y
                pdf.setFont('Helvetica-Bold', 10)
                pdf.drawString(margin_x, y, title)
                y -= 14
                pdf.setFont('Helvetica-Bold', 8)
                x = margin_x
                for header, width in headers:
                    pdf.drawString(x, y, header)
                    x += width
                y -= 12
                pdf.setFont('Helvetica', 8)
            x = margin_x
            for value, width in row:
                pdf.drawString(x, y, value)
                x += width
            y -= 12
        return y

    for student in students:
        statement = _build_statement(student, tenant, term=term, academic_year=academic_year)
        pdf.setFont('Helvetica-Bold', 12)
        pdf.drawString(margin_x, page_height - margin_y, 'Student Statement')
        pdf.setFont('Helvetica', 9)
        pdf.drawString(margin_x, page_height - margin_y - 16, f"Student: {student.get_full_name()}")
        pdf.drawString(margin_x, page_height - margin_y - 30, f"Admission: {student.admission_number}")
        pdf.drawString(margin_x, page_height - margin_y - 44, f"Class: {student.classroom or '—'}")
        pdf.drawString(margin_x, page_height - margin_y - 58, f"Term: {term} {academic_year}")
        pdf.drawString(margin_x, page_height - margin_y - 72, f"M-Pesa Paybill: {paybill}")
        pdf.drawString(margin_x, page_height - margin_y - 86, f"Account: {student.admission_number}")

        y = page_height - margin_y - 110
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(margin_x, y, 'Summary')
        y -= 14
        pdf.setFont('Helvetica', 9)
        pdf.drawString(margin_x, y, f"Total billed: KES {statement['summary']['total_billed']:,.2f}")
        y -= 12
        pdf.drawString(margin_x, y, f"Total paid: KES {statement['summary']['total_paid']:,.2f}")
        y -= 12
        pdf.drawString(margin_x, y, f"Total waived: KES {statement['summary']['total_waived']:,.2f}")
        y -= 12
        pdf.drawString(margin_x, y, f"Carried forward: KES {statement['summary']['carried_forward']:,.2f}")
        y -= 12
        pdf.drawString(margin_x, y, f"Balance due: KES {statement['balance_due']:,.2f}")
        y -= 18

        invoice_rows = []
        for inv in statement['invoices']:
            invoice_rows.append([
                (str(inv.fee_structure.term), 60),
                (str(inv.fee_structure.academic_year), 50),
                (f"KES {inv.total_due:,.2f}", 80),
                (f"KES {inv.waived_amount:,.2f}", 80),
                (f"KES {inv.paid_total:,.2f}", 80),
                (f"KES {inv.balance_amount:,.2f}", 80),
                (str(inv.status), 60),
            ])

        y = draw_table(
            'Invoices',
            [('Term', 60), ('Year', 50), ('Billed', 80), ('Waived', 80), ('Paid', 80), ('Balance', 80), ('Status', 60)],
            invoice_rows,
            y,
        )

        pdf.showPage()

    pdf.save()
    return response


@api_view(['POST'])
@permission_classes([IsAdminOrBursar])
def bulk_invoice_pdf(request):
    term = request.data.get('term')
    academic_year = request.data.get('academic_year')
    classroom_id = request.data.get('classroom')

    if not term or academic_year is None:
        return Response({'error': 'term and academic_year are required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        academic_year = int(academic_year)
    except (TypeError, ValueError):
        return Response({'error': 'academic_year must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        raise PermissionDenied('PDF generation must be under a school tenant.')

    qs = StudentFee.objects.filter(
        tenant=tenant,
        fee_structure__term=term,
        fee_structure__academic_year=academic_year,
    ).select_related('student', 'student__classroom', 'fee_structure')

    if classroom_id:
        qs = qs.filter(student__classroom_id=classroom_id)

    money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
    qs = qs.annotate(
        total_due=total_due_expression(),
        paid_total=Coalesce(
            Sum('payments__amount', filter=_confirmed_payment_filter()),
            money_zero,
        ),
    ).annotate(
        balance_amount=Case(
            When(paid_total__gte=F('total_due'), then=money_zero),
            default=F('total_due') - F('paid_total'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="invoice_slips.pdf"'

    pdf = canvas.Canvas(response, pagesize=A4)
    page_width, page_height = A4
    half_height = page_height / 2
    margin_x = 36
    margin_y = 28
    paybill = settings.MPESA.get('SHORTCODE', '')

    def draw_slip(y_top, invoice):
        student = invoice.student
        classroom = student.classroom
        pdf.setFont('Helvetica-Bold', 11)
        pdf.drawString(margin_x, y_top - margin_y, tenant.name)
        pdf.setFont('Helvetica', 9)
        pdf.drawString(margin_x, y_top - margin_y - 14, f"Student: {student.get_full_name()}")
        pdf.drawString(margin_x, y_top - margin_y - 28, f"Admission: {student.admission_number}")
        pdf.drawString(margin_x, y_top - margin_y - 42, f"Class: {classroom or '—'}")
        pdf.drawString(margin_x, y_top - margin_y - 56, f"Term: {invoice.fee_structure.term} {invoice.fee_structure.academic_year}")

        pdf.drawString(margin_x, y_top - margin_y - 80, f"Base fee: KES {invoice.expected_amount:,.2f}")
        pdf.drawString(margin_x, y_top - margin_y - 94, f"Carried forward: KES {invoice.carried_forward:,.2f}")
        pdf.drawString(margin_x, y_top - margin_y - 108, f"Total due: KES {invoice.total_due:,.2f}")
        pdf.drawString(margin_x, y_top - margin_y - 122, f"Amount paid: KES {invoice.paid_total:,.2f}")
        pdf.drawString(margin_x, y_top - margin_y - 136, f"Balance: KES {invoice.balance_amount:,.2f}")
        pdf.drawString(margin_x, y_top - margin_y - 150, f"Due date: {invoice.due_date}")

        pdf.drawString(margin_x, y_top - margin_y - 174, f"M-Pesa Paybill: {paybill}")
        pdf.drawString(margin_x, y_top - margin_y - 188, f"Account: {student.admission_number}")

        pdf.line(margin_x, y_top - half_height + margin_y - 6, page_width - margin_x, y_top - half_height + margin_y - 6)

    y_top = page_height
    slot = 0
    for invoice in qs:
        if slot == 0:
            y_top = page_height
        else:
            y_top = half_height
        draw_slip(y_top, invoice)
        slot += 1
        if slot == 2:
            pdf.showPage()
            slot = 0

    if slot != 0:
        pdf.showPage()

    pdf.save()
    return response


@api_view(['POST'])
@permission_classes([IsAdminOrBursar])
def bulk_sms(request):
    invoice_ids = request.data.get('invoice_ids') or []
    if not isinstance(invoice_ids, list) or not invoice_ids:
        return Response({'error': 'invoice_ids must be a non-empty list.'}, status=status.HTTP_400_BAD_REQUEST)

    tenant = getattr(request.user, 'tenant', None)
    invoices = (
        StudentFee.objects.filter(tenant=tenant, id__in=invoice_ids)
        .select_related('student', 'student__primary_guardian')
    )

    sent = 0
    failed = 0

    for invoice in invoices:
        guardian = invoice.student.primary_guardian
        if not guardian or not guardian.phone:
            failed += 1
            continue

        message = (
            f"Dear {guardian.full_name}, {invoice.student.get_full_name()} has a fee balance of "
            f"KES {invoice.balance:,.2f} for {invoice.fee_structure.term} {invoice.fee_structure.academic_year}. "
            "Please clear the balance."
        )
        log = SMSLog.objects.create(
            tenant=tenant,
            recipient_phone=guardian.phone,
            message=message,
            status='pending',
            provider='africas_talking',
        )
        send_sms_task.delay([guardian.phone], message, log.id)
        sent += 1

    return Response({'sent': sent, 'failed': failed})


@api_view(['POST'])
@permission_classes([IsAdminOrBursar])
def bulk_receipts_pdf(request):
    receipt_ids = request.data.get('receipt_ids') or []
    if not isinstance(receipt_ids, list) or not receipt_ids:
        return Response({'error': 'receipt_ids must be a non-empty list.'}, status=status.HTTP_400_BAD_REQUEST)

    tenant = getattr(request.user, 'tenant', None)
    receipts = (
        Receipt.objects.filter(tenant=tenant, id__in=receipt_ids)
        .select_related('student', 'payment')
        .order_by('-issued_at')
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="receipts.pdf"'

    pdf = canvas.Canvas(response, pagesize=A4)
    page_width, page_height = A4
    half_height = page_height / 2
    margin_x = 36
    margin_y = 28
    paybill = settings.MPESA.get('SHORTCODE', '')

    def draw_receipt(y_top, receipt):
        student = receipt.student
        pdf.setFont('Helvetica-Bold', 11)
        pdf.drawString(margin_x, y_top - margin_y, tenant.name)
        pdf.setFont('Helvetica', 9)
        pdf.drawString(margin_x, y_top - margin_y - 14, f"Receipt: {receipt.receipt_number}")
        pdf.drawString(margin_x, y_top - margin_y - 28, f"Student: {student.get_full_name()}")
        pdf.drawString(margin_x, y_top - margin_y - 42, f"Admission: {student.admission_number}")
        pdf.drawString(margin_x, y_top - margin_y - 56, f"Term: {receipt.term} {receipt.academic_year}")

        pdf.drawString(margin_x, y_top - margin_y - 80, f"Amount: KES {receipt.amount:,.2f}")
        pdf.drawString(margin_x, y_top - margin_y - 94, f"Method: {receipt.payment_method}")
        pdf.drawString(margin_x, y_top - margin_y - 108, f"Date: {receipt.issued_at.date()}")
        if receipt.payment and receipt.payment.mpesa_receipt_number:
            pdf.drawString(
                margin_x,
                y_top - margin_y - 122,
                f"M-Pesa receipt: {receipt.payment.mpesa_receipt_number}",
            )

        pdf.drawString(margin_x, y_top - margin_y - 146, f"M-Pesa Paybill: {paybill}")
        pdf.drawString(margin_x, y_top - margin_y - 160, f"Account: {student.admission_number}")

        pdf.line(margin_x, y_top - half_height + margin_y - 6, page_width - margin_x, y_top - half_height + margin_y - 6)

    y_top = page_height
    slot = 0
    for receipt in receipts:
        if slot == 0:
            y_top = page_height
        else:
            y_top = half_height
        draw_receipt(y_top, receipt)
        slot += 1
        if slot == 2:
            pdf.showPage()
            slot = 0

    if slot != 0:
        pdf.showPage()

    pdf.save()
    return response


class FeeStructureViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = FeeStructure.objects.select_related('tenant', 'classroom').all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAdminOrBursar]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['classroom', 'term', 'academic_year', 'is_active']
    search_fields = ['classroom__name', 'academic_year']
    def perform_create(self, serializer):
        try:
            super().perform_create(serializer)
        except IntegrityError:
            raise ValidationError(
                {'detail': 'Fee structure already exists for this class, term, and academic year.'}
            )


class StudentFeeViewSet(TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StudentFee.objects.select_related(
        'tenant',
        'student',
        'student__classroom',
        'fee_structure',
    ).all()
    serializer_class = StudentFeeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'student__classroom', 'fee_structure__term', 'fee_structure__academic_year']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']

    def get_queryset(self):
        qs = super().get_queryset()
        money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
        qs = qs.annotate(
            paid_total=Coalesce(
                Sum('payments__amount', filter=_confirmed_payment_filter()),
                money_zero,
            )
        )
        status_in = self.request.query_params.get('status__in')
        student_id = self.request.query_params.get('student')
        term = self.request.query_params.get('term')
        if status_in:
            qs = qs.filter(status__in=[item.strip() for item in status_in.split(',') if item.strip()])
        if student_id:
            qs = qs.filter(student_id=student_id)
        if term:
            qs = qs.filter(fee_structure__term=term)
        return qs.order_by(
            '-fee_structure__academic_year',
            'fee_structure__term',
            'student__admission_number',
        )

    @action(detail=False, methods=['post'], permission_classes=[IsAdminOrBursar])
    def generate_bulk(self, request):
        classroom_id = request.data.get('classroom')
        term = request.data.get('term')
        academic_year = request.data.get('academic_year')
        due_date = parse_date(str(request.data.get('due_date', '')))

        if not all([classroom_id, term, academic_year]):
            return Response(
                {'error': 'Missing required fields: classroom, term, academic_year.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            academic_year = int(academic_year)
        except (TypeError, ValueError):
            return Response({'error': 'Academic year must be a valid integer start year.'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = getattr(request.user, 'tenant', None)
        try:
            classroom = Classroom.objects.get(id=classroom_id, tenant=tenant)
            structure = FeeStructure.objects.get(
                classroom=classroom,
                term=term,
                academic_year=academic_year,
                tenant=tenant,
                is_active=True,
            )
        except Classroom.DoesNotExist:
            return Response({'error': 'Classroom not found.'}, status=status.HTTP_404_NOT_FOUND)
        except FeeStructure.DoesNotExist:
            return Response({'error': 'Active fee structure not found.'}, status=status.HTTP_404_NOT_FOUND)

        if StudentFee.objects.filter(tenant=tenant, fee_structure=structure).exists():
            return Response(
                {'error': 'Invoices already generated for this class, term, and academic year.'},
                status=status.HTTP_409_CONFLICT,
            )

        invoice_due_date = due_date or structure.due_date
        if not invoice_due_date:
            return Response(
                {'error': 'Missing due date. Set due_date on the fee structure or supply it in the request.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        students = Student.objects.filter(
            classroom=classroom,
            tenant=tenant,
            status=Student.Status.ACTIVE,
            is_active=True,
        )
        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for student in students:
                previous_fees = StudentFee.objects.select_related('fee_structure').filter(
                    tenant=tenant,
                    student=student,
                ).exclude(
                    fee_structure__term=term,
                    fee_structure__academic_year=academic_year,
                )
                for previous_fee in previous_fees:
                    _recalculate_invoice(previous_fee)

                carried_forward = get_carry_forward(student, term, academic_year)

                if structure.base_amount + carried_forward < Decimal('0.00'):
                    carried_forward = -structure.base_amount

                waived_amount, waiver = calculate_waived_amount(student, structure.base_amount, term, academic_year)
                
                if waived_amount == 0:
                    sibling_policy = get_sibling_discount(student)
                    if sibling_policy:
                        if sibling_policy.discount_type == 'percentage':
                            waived_amount = structure.base_amount * (sibling_policy.discount_value / Decimal('100'))
                        else:
                            waived_amount = min(sibling_policy.discount_value, structure.base_amount)
                        waived_amount = waived_amount.quantize(Decimal('0.01'))

                _, created = StudentFee.objects.get_or_create(
                    tenant=tenant,
                    student=student,
                    fee_structure=structure,
                    defaults={
                        'expected_amount': structure.base_amount,
                        'waived_amount': waived_amount,
                        'waiver': waiver,
                        'carried_forward': carried_forward,
                        'due_date': invoice_due_date,
                        'status': 'unpaid',
                    },
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        return Response(
            {
                'message': f'Bulk generation complete. {created_count} created, {skipped_count} skipped.',
                'created_count': created_count,
                'skipped_count': skipped_count,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrBursar])
    def defaulters(self, request):
        qs = (
            self.get_queryset()
            .annotate(outstanding=outstanding_expression())
            .filter(
                outstanding__gt=0,
                due_date__lt=timezone.localdate(),
                status__in=['unpaid', 'partial', 'overdue'],
            )
        )
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrBursar])
    def class_report(self, request):
        classroom_id = request.query_params.get('classroom')
        qs = self.get_queryset()
        if classroom_id:
            qs = qs.filter(student__classroom_id=classroom_id)

        money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
        money_field = DecimalField(max_digits=12, decimal_places=2)
        report = (
            qs.values('student__classroom__id', 'student__classroom__name')
            .annotate(
                expected_total=Coalesce(Sum(total_due_expression()), money_zero),
                collected_total=Coalesce(
                    Sum('payments__amount', filter=_confirmed_payment_filter()),
                    money_zero,
                ),
            )
            .annotate(
                outstanding=ExpressionWrapper(
                    F('expected_total') - F('collected_total'),
                    output_field=money_field,
                ),
            )
            .order_by('student__classroom__name')
        )
        return Response(list(report))

    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrBursar])
    def term_summary(self, request):
        qs = self.get_queryset()
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')
        if term:
            qs = qs.filter(fee_structure__term=term)
        if academic_year:
            try:
                academic_year = int(academic_year)
            except (TypeError, ValueError):
                return Response({'error': 'Academic year must be a valid integer start year.'}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(fee_structure__academic_year=academic_year)

        money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
        summary = qs.aggregate(
            expected_total=Coalesce(Sum(total_due_expression()), money_zero),
            collected_total=Coalesce(
                Sum('payments__amount', filter=_confirmed_payment_filter()),
                money_zero,
            ),
            total_waived=Coalesce(Sum('waived_amount'), money_zero),
        )
        summary['outstanding_total'] = summary['expected_total'] - summary['collected_total']
        return Response(summary)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrBursar])
    def dashboard_summary(self, request):
        qs = self.get_queryset()
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')
        if term:
            qs = qs.filter(fee_structure__term=term)
        if academic_year:
            try:
                academic_year = int(academic_year)
            except (TypeError, ValueError):
                return Response({'error': 'Academic year must be a valid integer start year.'}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(fee_structure__academic_year=academic_year)

        money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
        money_field = DecimalField(max_digits=12, decimal_places=2)
        summary = qs.aggregate(
            expected_total=Coalesce(Sum(total_due_expression()), money_zero),
            collected_total=Coalesce(
                Sum('payments__amount', filter=_confirmed_payment_filter()),
                money_zero,
            ),
            total_waived=Coalesce(Sum('waived_amount'), money_zero),
        )
        summary['outstanding_total'] = summary['expected_total'] - summary['collected_total']

        paid_qs = qs.annotate(
            paid_total=Coalesce(
                Sum('payments__amount', filter=_confirmed_payment_filter()),
                money_zero,
            )
        )
        defaulters_count = paid_qs.annotate(
            outstanding=outstanding_expression()
        ).filter(
            outstanding__gt=0,
            due_date__lt=timezone.localdate(),
            status__in=['unpaid', 'partial', 'overdue'],
        ).count()

        class_report = (
            qs.values('student__classroom__id', 'student__classroom__name')
            .annotate(
                expected_total=Coalesce(Sum(total_due_expression()), money_zero),
                collected_total=Coalesce(
                    Sum('payments__amount', filter=_confirmed_payment_filter()),
                    money_zero,
                ),
            )
            .annotate(
                outstanding=ExpressionWrapper(
                    F('expected_total') - F('collected_total'),
                    output_field=money_field,
                ),
            )
            .filter(outstanding__gt=0)
            .order_by('-outstanding')[:5]
        )

        payments_qs = Payment.objects.filter(tenant=getattr(request.user, 'tenant', None))
        if getattr(request.user, 'is_superuser', False) and not getattr(request.user, 'tenant', None):
            payments_qs = Payment.objects.all()
        recent_payments = payments_qs.select_related(
            'student',
            'student__classroom',
            'student_fee',
            'receipt',
            'recorded_by',
        ).order_by('-created_at')[:10]

        return Response({
            **summary,
            'defaulters_count': defaulters_count,
            'top_classes': list(class_report),
            'recent_payments': PaymentSerializer(recent_payments, many=True).data,
        })


class PaymentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('tenant', 'student', 'student_fee', 'recorded_by').all()
    serializer_class = PaymentSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'payment_method', 'student']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number', 'mpesa_receipt_number']

    def get_queryset(self):
        return super().get_queryset().select_related('receipt')

    def create(self, request, *args, **kwargs):
        idempotency_key = request.data.get('idempotency_key')
        tenant = getattr(request.user, 'tenant', None)
        if idempotency_key and Payment.objects.filter(tenant=tenant, idempotency_key=idempotency_key).exists():
            return Response(
                {'error': 'Payment already recorded for this school.'},
                status=status.HTTP_409_CONFLICT,
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        tenant = getattr(self.request.user, 'tenant', None)
        if not tenant and not getattr(self.request.user, 'is_superuser', False):
            raise PermissionDenied('Payments must be created under a school tenant.')

        student = serializer.validated_data.get('student')
        student_fee = serializer.validated_data.get('student_fee')
        if student and student.tenant_id != tenant.id:
            raise ValidationError({'student': 'Student does not belong to your school.'})
        if student_fee and student_fee.tenant_id != tenant.id:
            raise ValidationError({'student_fee': 'Invoice does not belong to your school.'})
        if student_fee and student_fee.student_id != student.id:
            raise ValidationError({'student_fee': 'Invoice does not belong to the selected student.'})

        try:
            serializer.save(tenant=tenant, recorded_by=self.request.user)
        except IntegrityError as exc:
            raise ValidationError({'idempotency_key': 'Payment already recorded.'}) from exc

    @action(detail=False, methods=['post'], permission_classes=[IsAdminOrBursar], url_path='manual')
    def manual(self, request):
        serializer = ManualPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            raise PermissionDenied('Manual payments must be recorded under a school tenant.')

        invoice = StudentFee.objects.select_related(
            'student',
            'student__primary_guardian',
            'student__classroom',
            'fee_structure',
        ).filter(id=data['invoice_id'], tenant=tenant).first()
        if not invoice:
            return Response({'error': 'Invoice not found.'}, status=status.HTTP_404_NOT_FOUND)

        amount = data['amount']

        payment_status = 'confirmed' if data['method'] in ('cash', 'bank') else 'pending'
        payment = Payment.objects.create(
            tenant=tenant,
            student=invoice.student,
            student_fee=invoice,
            amount=amount,
            payment_method=data['method'],
            status=payment_status,
            payment_date=data.get('date') or timezone.localdate(),
            bank_name=data.get('bank_name', ''),
            bank_reference=data.get('bank_reference', ''),
            cheque_number=data.get('cheque_number', ''),
            drawer_name=data.get('drawer_name', ''),
            notes=data.get('notes', ''),
            idempotency_key=str(uuid.uuid4()),
            recorded_by=request.user,
        )

        receipt = None
        if payment_status == 'confirmed':
            receipt = _create_receipt_for_payment(payment)
            invoice = _recalculate_invoice(invoice)
            if data.get('send_sms'):
                _send_payment_sms(invoice.student, amount, receipt.receipt_number, invoice.balance)

        return Response({
            'payment': PaymentSerializer(payment).data,
            'receipt_number': getattr(receipt, 'receipt_number', None),
            'updated_invoice': {
                'amount_due': str(max(Decimal('0.00'), invoice.expected_amount + invoice.carried_forward + invoice.penalty_amount - invoice.waived_amount)) if invoice else '0.00',
                'amount_paid': str(invoice.paid_amount) if invoice else '0.00',
                'balance': str(invoice.balance) if invoice else '0.00',
                'credit': str(invoice.credit) if invoice else '0.00',
                'status': invoice.status if invoice else 'unpaid',
            },
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrBursar], url_path='clear-cheque')
    def clear_cheque(self, request, pk=None):
        payment = self.get_queryset().select_related(
            'student',
            'student__primary_guardian',
            'student_fee',
            'student_fee__fee_structure',
        ).filter(pk=pk).first()
        if not payment:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)
        if payment.payment_method != 'cheque':
            return Response({'error': 'Only cheque payments can be cleared.'}, status=status.HTTP_400_BAD_REQUEST)

        payment.status = 'confirmed'
        if not payment.payment_date:
            payment.payment_date = timezone.localdate()
        payment.save(update_fields=['status', 'payment_date'])

        receipt = _create_receipt_for_payment(payment)
        invoice = _recalculate_invoice(payment.student_fee) if payment.student_fee else None
        if invoice:
            _send_payment_sms(invoice.student, payment.amount, receipt.receipt_number, invoice.balance)

        return Response({
            'payment': PaymentSerializer(payment).data,
            'receipt_number': receipt.receipt_number,
            'invoice': StudentFeeSerializer(invoice).data if invoice else None,
        })

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrBursar], url_path='bounce-cheque')
    def bounce_cheque(self, request, pk=None):
        payment = self.get_queryset().select_related(
            'student',
            'student__primary_guardian',
            'student_fee',
            'student_fee__fee_structure',
        ).filter(pk=pk).first()
        if not payment:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)
        if payment.payment_method != 'cheque':
            return Response({'error': 'Only cheque payments can be bounced.'}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get('reason')
        if not reason:
            return Response({'error': 'reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        payment.status = 'bounced'
        payment.notes = reason
        payment.save(update_fields=['status', 'notes'])

        try:
            payment.receipt.delete()
        except Receipt.DoesNotExist:
            pass

        invoice = _recalculate_invoice(payment.student_fee) if payment.student_fee else None
        guardian = getattr(payment.student, 'primary_guardian', None)
        if guardian and guardian.phone:
            message = (
                f"Dear {guardian.full_name}, cheque no. {payment.cheque_number} "
                f"for KES {payment.amount:,.2f} for {payment.student.get_full_name()} has bounced. "
                "Please visit the school to arrange payment."
            )
            log = SMSLog.objects.create(
                tenant=payment.student.tenant,
                recipient_phone=guardian.phone,
                message=message,
                status='pending',
                provider='africas_talking',
            )
            send_sms_task.delay([guardian.phone], message, log.id)

        return Response({
            'payment': PaymentSerializer(payment).data,
            'invoice': StudentFeeSerializer(invoice).data if invoice else None,
        })

    @action(detail=True, methods=['get'], permission_classes=[IsAdminBursarOrOwnParent], url_path='receipt/pdf')
    def receipt_pdf(self, request, pk=None):
        payment = self.get_queryset().select_related(
            'student',
            'student__primary_guardian',
            'student__classroom',
            'student_fee',
            'student_fee__fee_structure',
            'tenant',
            'receipt',
            'recorded_by',
        ).filter(pk=pk).first()
        if not payment:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.role == 'parent':
            guardian_user = getattr(getattr(payment.student, 'primary_guardian', None), 'user', None)
            if guardian_user != request.user:
                return Response({'error': 'Not allowed to access this receipt.'}, status=status.HTTP_403_FORBIDDEN)

        receipt_number = getattr(getattr(payment, 'receipt', None), 'receipt_number', None)
        if not receipt_number:
            return Response({'error': 'Receipt not found for this payment.'}, status=status.HTTP_404_NOT_FOUND)

        tenant = payment.tenant
        student = payment.student
        fee = payment.student_fee
        guardian = getattr(student, 'primary_guardian', None)
        classroom = student.classroom
        total_due = None
        base_amount = None
        carried_forward = None
        term = ''
        academic_year = ''
        if fee:
            base_amount = fee.expected_amount
            carried_forward = fee.carried_forward
            total_due = fee.expected_amount + fee.carried_forward + fee.penalty_amount - fee.waived_amount
            term = fee.fee_structure.term
            academic_year = fee.fee_structure.academic_year

        confirmed_total = Decimal('0.00')
        if fee:
            confirmed_total = (
                Payment.objects.filter(student_fee=fee, status__in=CONFIRMED_PAYMENT_STATUSES)
                .aggregate(total=Coalesce(Sum('amount'), Value(Decimal('0.00'))))
                .get('total')
                or Decimal('0.00')
            )
        remaining = (total_due - confirmed_total) if total_due is not None else Decimal('0.00')

        reference = '—'
        if payment.payment_method == 'bank':
            reference = payment.bank_reference or '—'
        elif payment.payment_method == 'cheque':
            reference = payment.cheque_number or '—'
        elif payment.payment_method == 'mpesa':
            reference = payment.mpesa_receipt_number or '—'

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="receipt_{receipt_number}.pdf"'

        pdf = canvas.Canvas(response, pagesize=A4)
        page_width, page_height = A4
        margin_x = 36
        margin_y = 36

        y = page_height - margin_y
        if tenant.logo:
            try:
                pdf.drawImage(ImageReader(tenant.logo.path), margin_x, y - 50, width=48, height=48, preserveAspectRatio=True)
            except Exception:
                pass
        pdf.setFont('Helvetica-Bold', 14)
        pdf.drawString(margin_x + 60, y - 20, tenant.name)
        pdf.setFont('Helvetica-Bold', 12)
        pdf.drawString(margin_x + 60, y - 38, 'OFFICIAL RECEIPT')

        y = y - 70
        pdf.setFont('Helvetica', 9)
        pdf.drawString(margin_x, y, f"Receipt No: {receipt_number}")
        payment_date = payment.payment_date or payment.created_at.date()
        pdf.drawString(margin_x + 250, y, f"Date: {payment_date}")
        y -= 12
        pdf.line(margin_x, y, page_width - margin_x, y)
        y -= 18

        pdf.drawString(margin_x, y, f"Received from: {guardian.full_name if guardian else '—'}")
        y -= 14
        pdf.drawString(margin_x, y, f"On behalf of:  {student.get_full_name()}")
        y -= 14
        pdf.drawString(margin_x, y, f"Admission No:  {student.admission_number}")
        y -= 14
        pdf.drawString(margin_x, y, f"Class:         {classroom or '—'}")
        y -= 12
        pdf.line(margin_x, y, page_width - margin_x, y)
        y -= 18

        pdf.drawString(margin_x, y, f"Term:          {term} {academic_year}")
        y -= 14
        pdf.drawString(margin_x, y, f"Base Fee:      KES {base_amount:,.2f}" if base_amount is not None else "Base Fee:      —")
        y -= 14
        pdf.drawString(margin_x, y, f"Carried Fwd:   KES {carried_forward:,.2f}" if carried_forward is not None else "Carried Fwd:   —")
        y -= 14
        pdf.drawString(margin_x, y, f"Total Due:     KES {total_due:,.2f}" if total_due is not None else "Total Due:     —")
        y -= 14
        pdf.drawString(margin_x, y, f"Amount Paid:   KES {payment.amount:,.2f}")
        y -= 14
        pdf.drawString(margin_x, y, f"Balance:       KES {remaining:,.2f}")
        y -= 12
        pdf.line(margin_x, y, page_width - margin_x, y)
        y -= 18

        pdf.drawString(margin_x, y, f"Payment Method: {payment.payment_method}")
        y -= 14
        pdf.drawString(margin_x, y, f"Reference:      {reference}")
        y -= 12
        pdf.line(margin_x, y, page_width - margin_x, y)
        y -= 18

        received_by = payment.recorded_by.get_full_name() if payment.recorded_by else '—'
        pdf.drawString(margin_x, y, f"Received by: {received_by}")
        y -= 20
        pdf.drawString(margin_x, y, "Signature: ___________________")
        y -= 30
        pdf.setFont('Helvetica-Oblique', 8)
        pdf.drawString(margin_x, y, f"This is an official receipt of {tenant.name}")

        pdf.showPage()
        pdf.save()
        return response


class ReceiptViewSet(TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Receipt.objects.select_related('tenant', 'student', 'payment', 'issued_by').all()
    serializer_class = ReceiptSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['student', 'academic_year', 'term']
    search_fields = ['receipt_number', 'student__first_name', 'student__last_name', 'student__admission_number']


class MpesaViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminOrBursar]

    def get_permissions(self):
        if self.action == 'callback':
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]

    @action(detail=False, methods=['post'])
    def stk_push(self, request):
        serializer = STKPushSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            raise PermissionDenied('M-Pesa payments must be initiated under a school tenant.')

        student = data['student']
        student_fee = data.get('student_fee')
        if student.tenant_id != tenant.id:
            raise ValidationError({'student': 'Student does not belong to your school.'})
        if student_fee:
            if student_fee.tenant_id != tenant.id:
                raise ValidationError({'student_fee': 'Invoice does not belong to your school.'})
            if student_fee.student_id != student.id:
                raise ValidationError({'student_fee': 'Invoice does not belong to the selected student.'})

        phone = self._normalize_phone(data['phone'])
        local_checkout_id = str(uuid.uuid4())
        try:
            response = MpesaService().initiate_stk_push(
                phone=phone,
                amount=data['amount'],
                account_ref=data.get('account_ref') or student.admission_number,
                description=data.get('description') or 'School Fee Payment',
            )
        except Exception as exc:
            payment = Payment.objects.create(
                tenant=tenant,
                student=student,
                student_fee=student_fee,
                amount=data['amount'],
                payment_method='mpesa',
                status='failed',
                mpesa_checkout_request_id=local_checkout_id,
                idempotency_key=local_checkout_id,
                recorded_by=request.user,
                notes=str(exc),
            )
            error_message = str(exc) or 'Could not initiate M-Pesa STK push.'
            return Response({'error': error_message}, status=status.HTTP_502_BAD_GATEWAY)

        if response.get('ResponseCode') == '0':
            daraja_checkout_id = response.get('CheckoutRequestID') or local_checkout_id
            payment = Payment.objects.create(
                tenant=tenant,
                student=student,
                student_fee=student_fee,
                amount=data['amount'],
                payment_method='mpesa',
                status='pending',
                mpesa_checkout_request_id=daraja_checkout_id,
                idempotency_key=daraja_checkout_id,
                recorded_by=request.user,
            )
            return Response({
                'success': True,
                'checkout_request_id': payment.mpesa_checkout_request_id,
                'payment_id': str(payment.id),
                'message': 'STK push sent. Enter your M-Pesa PIN on your phone.',
            }, status=status.HTTP_201_CREATED)

        failure_note = response.get('ResponseDescription') or response.get('errorMessage') or 'STK push failed.'
        Payment.objects.create(
            tenant=tenant,
            student=student,
            student_fee=student_fee,
            amount=data['amount'],
            payment_method='mpesa',
            status='failed',
            mpesa_checkout_request_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            recorded_by=request.user,
            notes=failure_note,
        )
        return Response({'error': failure_note}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='callback')
    def callback(self, request):
        result = MpesaService().process_callback(request.data)
        return Response(result)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        try:
            payment = Payment.objects.select_related('tenant', 'receipt').get(id=pk, tenant=request.user.tenant)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        payment = MpesaService().expire_stale_payment(payment)
        receipt_number = getattr(getattr(payment, 'receipt', None), 'receipt_number', None)
        return Response({
            'id': str(payment.id),
            'checkout_request_id': payment.mpesa_checkout_request_id,
            'status': payment.status,
            'amount': str(payment.amount),
            'receipt_number': receipt_number,
            'message': payment.notes,
        })

    def _normalize_phone(self, phone):
        phone = phone.strip().replace(' ', '')
        if phone.startswith('+'):
            phone = phone[1:]
        if phone.startswith('0'):
            phone = f'254{phone[1:]}'
        return phone


class WaiverPolicyViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = WaiverPolicy.objects.all()
    serializer_class = WaiverPolicySerializer
    permission_classes = [IsAdminOrBursar]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['description']

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """
        Get active waiver policies with student counts for dashboard.
        Returns list of policies with number of students assigned to each.
        """
        from django.db.models import Count
        
        tenant = request.user.tenant
        
        policies = WaiverPolicy.objects.filter(
            tenant=tenant,
            is_active=True,
        ).annotate(
            student_count=Count('student_waivers', filter=Q(student_waivers__is_active=True))
        ).values(
            'id', 'category', 'discount_type', 'discount_value', 'description', 'student_count', 'is_active', 'created_at'
        ).order_by('-created_at')
        
        return Response({
            'count': len(policies),
            'results': list(policies),
        })


class StudentWaiverViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = StudentWaiver.objects.select_related('student', 'policy', 'approved_by')
    serializer_class = StudentWaiverSerializer
    permission_classes = [IsAdminOrBursar]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['student__id', 'policy__category', 'is_active']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']

    def create(self, request, *args, **kwargs):
        """
        Assigning the same waiver again should reactivate the existing assignment.
        Otherwise old inactive rows hit the unique constraint and the dashboard
        keeps showing zero active students for that policy.
        """
        tenant = request.user.tenant
        student_id = request.data.get('student')
        policy_id = request.data.get('policy')

        if student_id and policy_id:
            student = Student.objects.filter(id=student_id, tenant=tenant).first()
            policy = WaiverPolicy.objects.filter(id=policy_id, tenant=tenant).first()
            if not student or not policy:
                raise ValidationError({'detail': 'Student or waiver policy was not found for this school.'})

            existing = StudentWaiver.objects.filter(
                tenant=tenant,
                student_id=student_id,
                policy_id=policy_id,
            ).first()
            if existing:
                data = request.data.copy()
                data['is_active'] = True
                serializer = self.get_serializer(existing, data=data, partial=True)
                serializer.is_valid(raise_exception=True)
                waiver = serializer.save(
                    tenant=tenant,
                    approved_by=request.user,
                    approved_on=timezone.localdate(),
                    is_active=True,
                )
                transaction.on_commit(lambda: apply_waiver_to_invoices(waiver))
                return Response(serializer.data, status=status.HTTP_200_OK)

        data = request.data.copy()
        data['is_active'] = True
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        waiver = serializer.save(
            tenant=self.request.user.tenant,
            approved_by=self.request.user,
            approved_on=timezone.localdate(),
            is_active=True,
        )
        transaction.on_commit(lambda: apply_waiver_to_invoices(waiver))

    def perform_update(self, serializer):
        waiver = serializer.save()
        transaction.on_commit(lambda: apply_waiver_to_invoices(waiver) if waiver.is_active else remove_waiver_from_invoices(waiver))

    def perform_destroy(self, instance):
        remove_waiver_from_invoices(instance)
        instance.delete()

    @action(detail=False, methods=['get'])
    def report(self, request):
        """
        Get waiver report summary.
        Returns total students with waivers, total waived amount this term.
        """
        tenant = request.user.tenant
        
        total_students_with_waivers = StudentWaiver.objects.filter(
            tenant=tenant,
            is_active=True,
        ).values('student_id').distinct().count()
        
        # Sum of all active waivers' applied amounts (estimated from StudentFee.waived_amount)
        total_waived = StudentFee.objects.filter(
            tenant=tenant,
            waiver__isnull=False,
        ).aggregate(total=Sum('waived_amount'))['total'] or Decimal('0.00')
        
        return Response({
            'total_students_with_waivers': total_students_with_waivers,
            'total_waived_amount': str(total_waived),
        })

    @action(detail=False, methods=['get'])
    def by_policy(self, request):
        """
        Get waivers by policy ID.
        Query param: policy_id (required)
        Returns list of students with waivers for the given policy.
        """
        policy_id = request.query_params.get('policy_id')
        if not policy_id:
            return Response({'error': 'policy_id query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        tenant = request.user.tenant
        try:
            waivers = StudentWaiver.objects.select_related(
                'student', 'policy', 'approved_by'
            ).filter(
                tenant=tenant,
                policy_id=policy_id,
                is_active=True,
            ).order_by('-created_at')
            
            serializer = StudentWaiverSerializer(
                waivers,
                many=True,
                context={'request': request},
            )
            return Response({
                'count': waivers.count(),
                'results': serializer.data,
            })
        except Exception as err:
            return Response({'error': str(err)}, status=status.HTTP_400_BAD_REQUEST)
