"""Statement and PDF generation views."""
from decimal import Decimal

from django.conf import settings
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from students.models import Student

from ..models import Payment, Receipt, StudentFee
from ..permissions import IsAdminBursarOrOwnParent, IsAdminOrBursar
from ..serializers import PaymentSerializer
from .mixins import (
    _confirmed_payment_filter,
    _create_receipt_for_payment,
    _recalculate_invoice,
    _send_payment_sms,
    outstanding_expression,
    total_due_expression,
)
from communication.models import SMSLog
from communication.sms import send_sms_task


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
        # total_billed = sum of base fees only, across all terms (shown in summary card)
        total_billed=Coalesce(Sum('expected_amount'), money_zero),
        total_penalty=Coalesce(Sum('penalty_amount'), money_zero),
        total_waived=Coalesce(Sum('waived_amount'), money_zero),
        total_paid=Coalesce(Sum('paid_total'), money_zero),
    )
    # CRITICAL: balance_due must NEVER sum each invoice's total_due (or carried_forward)
    # across multiple terms. carried_forward is a cascaded snapshot of prior terms'
    # debt -- it is already derived from those terms' own expected/penalty/waived
    # values. Summing total_due across terms counts the same arrears 2x, 3x, etc.
    # The only mathematically correct cross-term balance is:
    #   (sum of every term's OWN fee, net of its own penalty/waiver) - (all payments ever made)
    gross_billed = summary['total_billed'] + summary['total_penalty'] - summary['total_waived']
    total_balance = max(Decimal('0.00'), gross_billed - summary['total_paid'])

    # "Carried forward" in the summary card is informational only: it shows the
    # arrears that fed into the MOST RECENT term's invoice (not a sum across terms,
    # which would suffer the same double-counting problem described above).
    term_order = {'term1': 1, 'term2': 2, 'term3': 3, 'annual': 4}
    all_invoices_sorted = sorted(
        invoices_qs,
        key=lambda inv: (inv.fee_structure.academic_year, term_order.get(inv.fee_structure.term, 99)),
    )
    latest_carried_forward = all_invoices_sorted[-1].carried_forward if all_invoices_sorted else Decimal('0.00')

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
            'base_fee': str(inv.expected_amount),
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
            'carried_forward': str(latest_carried_forward),
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
        # total_billed = sum of each term's OWN fee only -- never sum total_due
        # (which embeds cascaded carried_forward) across multiple terms, or the
        # same arrears get counted 2x/3x. See student_statement() for full explanation.
        total_billed=Coalesce(Sum('expected_amount'), money_zero),
        total_penalty=Coalesce(Sum('penalty_amount'), money_zero),
        total_paid=Coalesce(Sum('paid_total'), money_zero),
        total_waived=Coalesce(Sum('waived_amount'), money_zero),
    )
    gross_billed = summary['total_billed'] + summary['total_penalty'] - summary['total_waived']
    balance_due = max(Decimal('0.00'), gross_billed - summary['total_paid'])

    term_order = {'term1': 1, 'term2': 2, 'term3': 3, 'annual': 4}
    _sorted_invoices = sorted(
        invoices_qs,
        key=lambda inv: (inv.fee_structure.academic_year, term_order.get(inv.fee_structure.term, 99)),
    )
    summary['carried_forward'] = _sorted_invoices[-1].carried_forward if _sorted_invoices else Decimal('0.00')

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
                pdf.drawString(x, y, str(value))
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
            (f"KES {inv.expected_amount:,.2f}", 80),
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
        [('Date', 65), ('Amount', 75), ('Method', 55), ('Receipt', 160), ('M-Pesa', 90)],
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
                (f"KES {inv.expected_amount:,.2f}", 80),
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