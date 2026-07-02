"""Payment, receipt, and M-Pesa viewsets."""
import uuid
from decimal import Decimal

from django.db import IntegrityError
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from students.models import Student

from ..models import CONFIRMED_PAYMENT_STATUSES, Payment, Receipt, StudentFee
from ..mpesa import MpesaService
from ..permissions import IsAdminBursarOrOwnParent, IsAdminOrBursar
from ..serializers import PaymentSerializer, ReceiptSerializer , StudentFeeSerializer
from .mixins import (
    TenantScopedMixin,
    _create_receipt_for_payment,
    _recalculate_invoice,
    _send_payment_sms,
)
from communication.models import SMSLog
from communication.sms import send_sms_task


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
        from .mixins import ManualPaymentSerializer
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

        # ── BUG FIX: Prevent overpayment beyond current balance ──
        # If invoice already has credit from previous terms, allow paying up to
        # balance + credit. Otherwise cap at current balance.
        current_balance = invoice.balance
        current_credit = invoice.credit
        max_payable = current_balance + current_credit

        if amount > max_payable:
            raise ValidationError({
                'amount': (
                    f'Payment of KES {amount:,.2f} exceeds the maximum payable amount of '
                    f'KES {max_payable:,.2f} for this invoice. '
                    f'(Balance: KES {current_balance:,.2f}, Available credit: KES {current_credit:,.2f})'
                )
            })
        # ── END BUG FIX ──

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

            from ..utils import recalculate_student_fees
            recalculate_student_fees(invoice.student)
            
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
            from ..utils import recalculate_student_fees
            recalculate_student_fees(invoice.student)
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
        if invoice:
            from ..utils import recalculate_student_fees
            recalculate_student_fees(invoice.student)
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
    throttle_scope = 'mpesa_stk'

    def get_permissions(self):
        if self.action == 'callback':
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]

    def get_throttles(self):
        if self.action == 'stk_push':
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=['post'])
    def stk_push(self, request):
        from .mixins import STKPushSerializer
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

        # ── BUG FIX: Prevent M-Pesa overpayment ──
        if student_fee:
            current_balance = student_fee.balance
            current_credit = student_fee.credit
            max_payable = current_balance + current_credit
            if data['amount'] > max_payable:
                raise ValidationError({
                    'amount': (
                        f'Payment of KES {data["amount"]:,.2f} exceeds the maximum payable amount of '
                        f'KES {max_payable:,.2f} for this invoice. '
                        f'(Balance: KES {current_balance:,.2f}, Available credit: KES {current_credit:,.2f})'
                    )
                })
        # ── END BUG FIX ──

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
        
        # Human-friendly status messages for frontend
        status_messages = {
            'pending': 'Waiting for M-Pesa confirmation...',
            'completed': 'Payment successful!',
            'cancelled': 'Transaction cancelled by user.',
            'expired': 'Payment timed out. Please try again.',
            'failed': payment.notes or 'Payment failed. Please try again.',
        }
        
        return Response({
            'id': str(payment.id),
            'checkout_request_id': payment.mpesa_checkout_request_id,
            'status': payment.status,
            'amount': str(payment.amount),
            'receipt_number': receipt_number,
            'message': status_messages.get(payment.status, payment.notes),
        })
    def _normalize_phone(self, phone):
        phone = phone.strip().replace(' ', '')
        if phone.startswith('+'):
            phone = phone[1:]
        if phone.startswith('0'):
            phone = f'254{phone[1:]}'
        return phone