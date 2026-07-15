"""Payment, receipt, and M-Pesa viewsets."""
import logging
import re
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, AnonRateThrottle
from rest_framework.views import APIView

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from students.models import Student
from tenants.models import Tenant
from ..models import CONFIRMED_PAYMENT_STATUSES, Payment, Receipt, StudentFee, PaymentLog
from ..mpesa import MpesaService, MpesaSTKPushError, MpesaConfigurationError
from ..permissions import TenantAwarePermission, IsAdminBursarOrOwnParent, IsAdminOrBursar
from ..serializers import PaymentSerializer, ReceiptSerializer, StudentFeeSerializer, MpesaInitiateSerializer
from ..tasks import query_mpesa_status_task
from .mixins import (
    TenantScopedMixin,
    _create_receipt_for_payment,
    _recalculate_invoice,
    _send_payment_sms,
)
from communication.models import SMSLog
from communication.sms import send_sms_task

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Custom throttle for M-Pesa callback webhook
# ─────────────────────────────────────────────────────────────
class MpesaCallbackThrottle(AnonRateThrottle):
    """Rate limit for Safaricom callback endpoint."""
    rate = '100/minute'


class MpesaCallbackWebhookView(APIView):
    """
    Receives M-Pesa callbacks from Safaricom.
    Must be open (no auth) because Safaricom calls it directly.
    Tenant isolation is enforced by looking up the Payment by CheckoutRequestID.

    SECURITY:
    - IP logging for audit trail (unknown IPs are logged but not blocked)
    - Replay protection via PaymentLog deduplication
    - Rate limiting via MpesaCallbackThrottle
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [MpesaCallbackThrottle]

    # Known Safaricom IPs (production + sandbox) for logging purposes
    KNOWN_IPS = getattr(settings, 'MPESA_ALLOWED_IPS', [
        '196.201.214.200', '196.201.214.206',
        '196.201.213.114', '196.201.214.207',
    ])

    def _get_client_ip(self, request):
        """Extract real client IP, handling proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '').strip()

    def post(self, request, *args, **kwargs):
        remote_ip = self._get_client_ip(request)

        # Log all callback IPs for audit trail
        if remote_ip not in self.KNOWN_IPS:
            logger.warning(
                f"M-Pesa callback received from unknown IP: {remote_ip}. "
                f"Processing anyway for production stability."
            )
        else:
            logger.info(f"M-Pesa callback received from known IP: {remote_ip}")

        payload = request.data
        logger.info(f"M-Pesa callback received: {payload}")

        stk_callback = payload.get("Body", {}).get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")

        if not checkout_id:
            logger.error("Callback missing CheckoutRequestID")
            return Response(
                {"ResultCode": 1, "ResultDesc": "Missing structural verification identifiers"},
                status=status.HTTP_200_OK  # Return 200 so Safaricom doesn't retry
            )

        # ── Replay Protection ──
        # Check if we've already processed this exact callback
        if PaymentLog.objects.filter(
            checkout_request_id=checkout_id,
            event_type='callback',
            result_code=str(result_code)
        ).exists():
            logger.info(f"Duplicate callback ignored for checkout_id: {checkout_id}")
            return Response(
                {"ResultCode": 0, "ResultDesc": "Duplicate callback ignored"},
                status=status.HTTP_200_OK
            )

        # Find payment to determine tenant (multi-tenant isolation)
        payment = (
            Payment.objects
            .filter(mpesa_checkout_request_id=checkout_id)
            .select_related('tenant')
            .first()
        )

        if not payment:
            # Orphan callback - log it for manual reconciliation
            PaymentLog.objects.create(
                tenant=None,
                payment=None,
                checkout_request_id=checkout_id,
                event_type='callback_orphan',
                payload=payload,
            )
            logger.error(f"Orphan callback or trace mismatch for checkout_id: {checkout_id}")
            return Response(
                {"ResultCode": 1, "ResultDesc": "Tenant data trace mismatch"},
                status=status.HTTP_200_OK
            )

        # Process via tenant-specific service
        try:
            service = MpesaService(school_slug=payment.tenant.slug)
            result = service.process_callback(payload)
            return Response(
                {"ResultCode": 0, "ResultDesc": "Callback processed and archived safely."},
                status=status.HTTP_200_OK
            )
        except MpesaConfigurationError as e:
            logger.error(f"M-Pesa configuration error for tenant {payment.tenant.slug}: {e}")
            return Response(
                {"ResultCode": 1, "ResultDesc": "Configuration error mapping."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception(f"Unexpected error processing callback: {e}")
            return Response(
                {"ResultCode": 1, "ResultDesc": "Internal application logic error occurred."},
                status=status.HTTP_200_OK
            )


class PaymentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('tenant', 'student', 'student_fee', 'recorded_by').all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, TenantAwarePermission]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'payment_method', 'student']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number', 'mpesa_receipt_number']

    def get_queryset(self):
        """Tenant-isolated queryset with enhanced prefetches."""
        tenant = self._get_tenant()
        if not tenant:
            return Payment.objects.none()
        return Payment.objects.filter(tenant=tenant).select_related(
            'student', 'student_fee', 'student_fee__fee_structure', 'recorded_by', 'receipt'
        ).prefetch_related('logs')

    def _get_tenant(self):
        return getattr(self.request, 'tenant', None) or getattr(self.request.user, 'tenant', None)

    def perform_create(self, serializer):
        tenant = self._get_tenant()
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

    @action(detail=True, methods=['post'])
    def retry_query(self, request, pk=None):
        """Manually trigger an asynchronous status query for a pending payment."""
        payment = self.get_object()
        if payment.status.lower() not in ['pending']:
            return Response(
                {"error": f"Payment is {payment.status}, not pending."},
                status=status.HTTP_400_BAD_REQUEST
            )

        query_mpesa_status_task.delay(payment.id)
        return Response({"status": "queued", "message": "Status query scheduled."})

    @action(detail=False, methods=['post'], permission_classes=[IsAdminOrBursar], url_path='manual')
    def manual(self, request):
        from .mixins import ManualPaymentSerializer
        serializer = ManualPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant = getattr(self.request, 'tenant', None) or getattr(self.request.user, 'tenant', None)
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
            'student', 'student__primary_guardian', 'student_fee', 'student_fee__fee_structure'
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
            _send_payment_sms(invoice.student, payment.amount, receipt.receipt_number, invoice.balance)

        return Response({
            'payment': PaymentSerializer(payment).data,
            'receipt_number': receipt.receipt_number,
            'invoice': StudentFeeSerializer(invoice).data if invoice else None,
        })

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrBursar], url_path='bounce-cheque')
    def bounce_cheque(self, request, pk=None):
        payment = self.get_queryset().select_related(
            'student', 'student__primary_guardian', 'student_fee', 'student_fee__fee_structure'
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
            'student', 'student__primary_guardian', 'student__classroom',
            'student_fee', 'student_fee__fee_structure', 'tenant', 'receipt', 'recorded_by'
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

        tenant, student, fee = payment.tenant, payment.student, payment.student_fee
        guardian, classroom = getattr(student, 'primary_guardian', None), student.classroom
        total_due, base_amount, carried_forward, term, academic_year = None, None, None, '', ''

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
                .get('total') or Decimal('0.00')
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
        margin_x, margin_y = 36, 36

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

        y -= 70
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


class MpesaViewSet(TenantScopedMixin, viewsets.ViewSet):
    permission_classes = [IsAuthenticated, TenantAwarePermission]
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
        """
        Initiate M-Pesa STK push.
        Creates a Payment record FIRST, then calls Daraja to safeguard multi-tenant callback delivery.

        SECURITY:
        - Validates amount against invoice balance (prevents under/over-payment)
        - Client-supplied idempotency key prevents duplicate STK pushes
        - 24h deduplication window for idempotency keys
        """
        serializer = MpesaInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
        if not tenant:
            raise PermissionDenied('M-Pesa payments must be initiated under a school tenant.')

        student = get_object_or_404(Student, id=data['student_id'], tenant=tenant)
        fee = None
        if data.get('fee_id'):
            fee = get_object_or_404(StudentFee, id=data['fee_id'], tenant=tenant, student=student)

        # ── Amount Validation Against Invoice ──
        if fee:
            invoice_balance = fee.effective_balance
            amount = data['amount']

            # Prevent underpayment (must be at least 1 KES - already validated by serializer)
            if amount < Decimal('1.00'):
                return Response({
                    'error': 'Amount must be at least KES 1.00.',
                    'error_code': 'AMOUNT_TOO_SMALL'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Prevent overpayment beyond 5% of invoice balance (allows small credit)
            max_allowed = invoice_balance * Decimal('1.05')
            if amount > max_allowed and invoice_balance > 0:
                return Response({
                    'error': f'Amount exceeds invoice balance of KES {invoice_balance:.2f}. Maximum allowed: KES {max_allowed:.2f}',
                    'error_code': 'AMOUNT_EXCEEDS_BALANCE',
                    'invoice_balance': str(invoice_balance),
                    'max_allowed': str(max_allowed),
                }, status=status.HTTP_400_BAD_REQUEST)

        phone = self._normalize_phone(data['phone'])

        # ── Idempotency: Client-Supplied Key with Deduplication ──
        idempotency_key = data.get('idempotency_key')
        if idempotency_key:
            # Check for existing payment with same key in last 24 hours
            existing = Payment.objects.filter(
                tenant=tenant,
                idempotency_key=idempotency_key,
                created_at__gte=timezone.now() - timezone.timedelta(hours=24)
            ).first()
            if existing:
                return Response({
                    'success': True,
                    'payment_id': str(existing.id),
                    'checkout_request_id': existing.mpesa_checkout_request_id,
                    'merchant_request_id': existing.mpesa_merchant_request_id,
                    'message': 'Payment already initiated. Please check your phone for the M-Pesa prompt.',
                    'duplicate': True,
                }, status=status.HTTP_200_OK)
        else:
            # Fallback: generate server-side key
            idempotency_key = f"{tenant.slug}-{uuid.uuid4().hex}"

        # Create localized initial trace state to catch transactional boundaries
        payment = Payment.objects.create(
            tenant=tenant,
            student=student,
            student_fee=fee,
            amount=data['amount'],
            payment_method='mpesa',
            status='pending',
            phone_number=phone,
            idempotency_key=idempotency_key,
            recorded_by=request.user,
        )

        try:
            mpesa = MpesaService(school_slug=tenant.slug)
            response = mpesa.initiate_stk_push(
                phone=phone,
                amount=int(data['amount']),
                invoice_id=str(payment.id)[:8],
                description=f"School fees for {student.admission_number}",
                idempotency_key=idempotency_key,
                account_ref=student.admission_number,
            )

            if str(response.get('ResponseCode')) == '0':
                payment.mpesa_checkout_request_id = response.get('CheckoutRequestID', '')
                payment.mpesa_merchant_request_id = response.get('MerchantRequestID', '')
                payment.save(update_fields=['mpesa_checkout_request_id', 'mpesa_merchant_request_id'])

                # Schedule fallback evaluation tasks asynchronously
                query_mpesa_status_task.apply_async(args=[payment.id], countdown=60) 
                query_mpesa_status_task.apply_async(args=[payment.id], countdown=180)

                return Response({
                    'success': True,
                    'payment_id': str(payment.id),
                    'checkout_request_id': payment.mpesa_checkout_request_id,
                    'merchant_request_id': payment.mpesa_merchant_request_id,
                    'message': 'STK push initiated. Please check your phone and enter your M-Pesa PIN.'
                }, status=status.HTTP_201_CREATED)

            else:
                failure_note = response.get('ResponseDescription') or response.get('errorMessage') or 'STK push failed.'
                payment.status = 'failed'
                payment.failure_reason = failure_note
                payment.notes = failure_note
                payment.failed_at = timezone.now()
                payment.save()
                return Response({'error': failure_note}, status=status.HTTP_400_BAD_REQUEST)

        except MpesaSTKPushError as e:
            error_msg = str(e)
            error_code = 'STK_PUSH_FAILED'

            # Map known Safaricom/Daraja error messages to user-friendly text
            error_lower = error_msg.lower()
            if 'insufficient' in error_lower or 'dsuser has insufficient balance' in error_lower:
                error_code = '1'
                error_msg = 'You do not have enough M-Pesa funds for this transaction.'
            elif 'cancelled' in error_lower or 'cancel' in error_lower:
                error_code = '1032'
                error_msg = 'You cancelled the payment on your phone.'
            elif 'timeout' in error_lower or 'timed out' in error_lower:
                error_code = '1037'
                error_msg = 'The payment request timed out. Please try again.'
            elif 'wrong pin' in error_lower or 'pin' in error_lower:
                error_code = '2006'
                error_msg = 'Wrong M-Pesa PIN entered.'
            elif 'invalid' in error_lower and 'number' in error_lower:
                error_code = '1001'
                error_msg = 'Invalid phone number or M-Pesa account issue.'
            elif 'configuration' in error_lower or 'caller information' in error_lower:
                error_code = 'CONFIGURATION_ERROR'
                error_msg = 'M-Pesa is not set up for this school. Please contact the bursar.'

            payment.status = 'failed'
            payment.failure_reason = error_msg
            payment.notes = f"STK push rejected by Safaricom: {error_msg} (original: {str(e)})"
            payment.failed_at = timezone.now()
            payment.save()
            return Response({
                'success': False,
                'error': error_msg,
                'error_code': error_code,
                'payment_id': str(payment.id),
            }, status=status.HTTP_400_BAD_REQUEST)

        except MpesaConfigurationError as e:
            payment.status = 'failed'
            payment.failure_reason = "M-Pesa not configured for this school."
            payment.mpesa_result_code = 'CONFIGURATION_ERROR'
            payment.notes = str(e)
            payment.failed_at = timezone.now()
            payment.save()
            return Response({
                'success': False,
                'error': 'M-Pesa is not properly configured for this school. Please contact support.',
                'error_code': 'CONFIGURATION_ERROR',
                'payment_id': str(payment.id),
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        except Exception as exc:
            payment.status = 'failed'
            payment.failure_reason = f"System error: {str(exc)}"
            payment.mpesa_result_code = 'INTERNAL_ERROR'
            payment.notes = payment.failure_reason
            payment.failed_at = timezone.now()
            payment.save()
            logger.exception(f"Unexpected error during STK push for payment {payment.id}")
            return Response({
                'success': False,
                'error': 'An unexpected error occurred. Please try again later.',
                'error_code': 'INTERNAL_ERROR',
                'payment_id': str(payment.id),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='callback')
    def callback(self, request):
        """Fallback callback route targeting structured verification configurations."""
        payload = request.data
        checkout_id = payload.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
        if not checkout_id:
            return Response({'error': 'Missing CheckoutRequestID'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.select_related('tenant').get(mpesa_checkout_request_id=checkout_id)
            mpesa = MpesaService(school_slug=payment.tenant.slug)
            result = mpesa.process_callback(payload)
            return Response(result)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Callback trace error: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        try:
            tenant = getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)
            payment = Payment.objects.select_related('tenant', 'receipt').get(id=pk, tenant=tenant)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        mpesa = MpesaService(school_slug=payment.tenant.slug)
        payment = mpesa.expire_stale_payment(payment)

        receipt_number = getattr(getattr(payment, 'receipt', None), 'receipt_number', None)

        status_messages = {
            'pending': 'Waiting for M-Pesa confirmation...',
            'completed': 'Payment successful!',
            'cancelled': 'Transaction cancelled by user.',
            'expired': 'Payment timed out. Please try again.',
            'failed': payment.notes or 'Payment failed. Please try again.',
            'FAILED': payment.notes or 'Payment failed. Please try again.',
            'COMPLETED': 'Payment successful!',
        }

        final_statuses = ['completed', 'COMPLETED', 'cancelled', 'expired', 'failed', 'FAILED']
        stop_polling = payment.status in final_statuses

        return Response({
            'id': str(payment.id),
            'checkout_request_id': payment.mpesa_checkout_request_id,
            'status': payment.status,
            'amount': str(payment.amount),
            'receipt_number': receipt_number,
            'result_code': payment.mpesa_result_code or None,
            'message': status_messages.get(payment.status, payment.notes or 'Unknown status'),
            'stop_polling': stop_polling,
        })

    def _normalize_phone(self, phone):
        """
        Normalize Kenyan phone numbers to 254XXXXXXXXX format.
        Supports legacy 07xx and newer 01xx Safaricom prefixes.
        """
        if not phone:
            return ''
        digits = re.sub(r'\D', '', str(phone))
        if digits.startswith('0') and len(digits) == 10:
            return '254' + digits[1:]
        if digits.startswith('7') and len(digits) == 9:
            return '254' + digits
        if digits.startswith('1') and len(digits) == 9:
            return '254' + digits
        if digits.startswith('254') and len(digits) == 12:
            return digits
        return digits  # Fallback: return stripped digits

        