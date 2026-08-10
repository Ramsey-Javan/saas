import base64
import hashlib
import logging
import re
from contextlib import contextmanager
from decimal import Decimal
from datetime import datetime

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from tenants.models import Tenant as SchoolTenant
from .models import CONFIRMED_PAYMENT_STATUSES, Payment, Receipt, StudentFee, PaymentLog

logger = logging.getLogger(__name__)


class MpesaConfigurationError(Exception):
    """Raised when M-Pesa credentials are missing or invalid."""
    pass


class MpesaSTKPushError(Exception):
    """Raised when STK push fails at Safaricom level."""
    pass


class MpesaService:
    # Known Daraja result codes and user-friendly messages
    RESULT_CODE_MAP = {
        "0": ("Success", "completed"),
        "1": ("Insufficient funds or M-Pesa account issue.", "failed"),
        "1032": ("Transaction cancelled by user on phone.", "failed"),
        "1037": ("STK push timed out. User did not respond.", "expired"),
        "2006": ("Wrong M-Pesa PIN entered.", "failed"),
        "2001": ("Invalid parameters or credentials.", "failed"),
        "1001": ("Invalid phone number or service rejected.", "failed"),
        "1019": ("Transaction already exists / duplicate.", "ignored"),
    }

    # Timeout from settings, with fallback
    TIMEOUT_SECONDS = getattr(settings, 'MPESA_TIMEOUT_SECONDS', 90)
    TOKEN_CACHE_TTL = 3000  # 50 minutes (Safaricom tokens valid 1 hour)
    TENANT_CACHE_TTL = 300  # 5 minutes

    def __init__(self, school_slug: str):
        """
        Initialize the service per tenant. Each school maintains its own
        isolated Daraja credentials for multi-tenant isolation.
        Falls back to global settings (the MPESA dict) if tenant fields are missing.
        Uses Redis caching to avoid DB hits on every call.
        """
        self.school_slug = school_slug
        self._load_tenant_config()

        if self.env == 'production':
            self.base_url = "https://api.safaricom.co.ke"
        else:
            self.base_url = "https://sandbox.safaricom.co.ke"

        self._access_token = None

    def _load_tenant_config(self):
        """Load tenant config from cache or DB."""
        cache_key = f'mpesa:tenant:{self.school_slug}'
        cached = cache.get(cache_key)

        if cached:
            self.tenant_id = cached['tenant_id']
            self.consumer_key = cached['consumer_key']
            self.consumer_secret = cached['consumer_secret']
            self.shortcode = cached['shortcode']
            self.passkey = cached['passkey']
            self.env = cached['env']
            self.callback_url = cached['callback_url']
            # Re-fetch tenant object only when needed (signals, etc.)
            self._tenant = None
            return

        try:
            tenant = SchoolTenant.objects.get(slug=self.school_slug)
        except SchoolTenant.DoesNotExist as exc:
            raise MpesaConfigurationError(f"Tenant '{self.school_slug}' not found.") from exc

        self._tenant = tenant
        self.tenant_id = tenant.id

        # Try tenant-specific credentials, fallback to settings.MPESA
        self.consumer_key = (
            getattr(tenant, 'mpesa_consumer_key', None)
            or settings.MPESA.get('CONSUMER_KEY')
        )
        self.consumer_secret = (
            getattr(tenant, 'mpesa_consumer_secret', None)
            or settings.MPESA.get('CONSUMER_SECRET')
        )
        self.shortcode = (
            getattr(tenant, 'mpesa_shortcode', None)
            or settings.MPESA.get('SHORTCODE')
        )
        self.passkey = (
            getattr(tenant, 'mpesa_passkey', None)
            or settings.MPESA.get('PASSKEY')
        )
        self.env = (
            getattr(tenant, 'mpesa_env', None)
            or settings.MPESA.get('ENV', 'sandbox')
        )
        self.callback_url = (
            getattr(tenant, 'mpesa_callback_url', None)
            or settings.MPESA.get('CALLBACK_URL')
        )

        # Cache for 5 minutes
        cache.set(cache_key, {
            'tenant_id': self.tenant_id,
            'consumer_key': self.consumer_key,
            'consumer_secret': self.consumer_secret,
            'shortcode': self.shortcode,
            'passkey': self.passkey,
            'env': self.env,
            'callback_url': self.callback_url,
        }, timeout=self.TENANT_CACHE_TTL)

    @property
    def tenant(self):
        """Lazy-load tenant object when needed (not during __init__)."""
        if self._tenant is None:
            self._tenant = SchoolTenant.objects.get(id=self.tenant_id)
        return self._tenant

    def _is_placeholder(self, value):
        if not value:
            return True
        normalized = str(value).strip().lower()
        return normalized.startswith('your-') or 'change-in-production' in normalized

    def _ensure_configured(self):
        missing = [
            name for name, value in {
                'MPESA_CONSUMER_KEY': self.consumer_key,
                'MPESA_CONSUMER_SECRET': self.consumer_secret,
                'MPESA_SHORTCODE': self.shortcode,
                'MPESA_PASSKEY': self.passkey,
            }.items()
            if self._is_placeholder(value)
        ]
        if missing:
            raise MpesaConfigurationError(
                f'Missing M-Pesa configuration for tenant {self.school_slug}: {", ".join(missing)}'
            )

    @contextmanager
    def _advisory_lock(self, lock_id: int):
        """PostgreSQL advisory lock for cross-process synchronization."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [lock_id])
            try:
                yield
            finally:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])

    def _payment_lock_id(self, payment_id) -> int:
        """Generate a consistent 32-bit lock ID from a UUID."""
        # UUID.int is 128-bit; mod down to 32-bit signed integer range
        return (int(payment_id) % 2147483647)

    def get_access_token(self) -> str:
        """Fetches the OAuth access token from Safaricom, with Redis caching."""
        self._ensure_configured()

        # Check Redis cache first
        cache_key = f'mpesa:token:{self.school_slug}'
        cached_token = cache.get(cache_key)
        if cached_token:
            logger.debug(f"Using cached M-Pesa token for tenant {self.school_slug}")
            return cached_token

        if self._access_token:
            return self._access_token

        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        try:
            res = requests.get(url, auth=(self.consumer_key, self.consumer_secret), timeout=10)
            res.raise_for_status()
            self._access_token = res.json()["access_token"]
            # Cache token for 50 minutes (Safaricom tokens valid 1 hour)
            cache.set(cache_key, self._access_token, timeout=self.TOKEN_CACHE_TTL)
            return self._access_token
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch M-Pesa token for tenant {self.school_slug}: {str(e)}")
            raise MpesaSTKPushError(f"Unable to connect to M-Pesa. Please try again later.") from e

    def generate_password(self):
        """Generates dynamic base64 string password using shortcode, passkey and timestamp."""
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        if hasattr(settings, 'generate_mpesa_password'):
            password = str(settings.generate_mpesa_password(self.shortcode, self.passkey, timestamp))
            return password, timestamp

        raw = f"{self.shortcode}{self.passkey}{timestamp}"
        return base64.b64encode(raw.encode()).decode("utf-8"), timestamp

    @staticmethod
    def validate_and_normalize_phone(phone: str) -> str:
        """
        Validates and normalizes a Kenyan phone number to 254XXXXXXXXX.
        Supports both legacy 07xx and newer 01xx Safaricom prefixes.
        Raises ValueError if invalid.
        """
        if not phone:
            raise ValueError("Phone number is required.")

        # Remove all non-digits (spaces, dashes, plus signs, etc.)
        digits = re.sub(r'\D', '', str(phone))

        # Normalize common Kenyan formats to 254XXXXXXXXX
        if digits.startswith('0') and len(digits) == 10:
            digits = '254' + digits[1:]
        elif digits.startswith('7') and len(digits) == 9:
            digits = '254' + digits
        elif digits.startswith('1') and len(digits) == 9:
            digits = '254' + digits
        elif digits.startswith('254') and len(digits) == 12:
            pass  # Already normalized
        else:
            raise ValueError(
                "Invalid Kenyan phone number. Expected formats: "
                "07XX XXX XXX, 01XX XXX XXX, 7XX XXX XXX, 1XX XXX XXX, "
                "2547XX XXX XXX, 2541XX XXX XXX, or +2547XX XXX XXX."
            )

        # Validate Safaricom prefix: must start with 2547 or 2541 followed by 8 digits
        if not re.match(r'^254[71]\d{8}$', digits):
            raise ValueError(
                "Invalid Safaricom number format. "
                "Must start with 07, 01, 7, 1, 2547, or 2541."
            )

        return digits

    def initiate_stk_push(
        self,
        phone: str,
        amount: int,
        invoice_id: str,
        description: str = "",
        idempotency_key: str = "",
        account_ref: str = "",
    ) -> dict:
        """
        Initiates an STK push. Validates phone, handles Daraja errors, and returns structured response.
        """
        # Validate and normalize phone
        normalized_phone = self.validate_and_normalize_phone(phone)

        token = self.get_access_token()
        password, timestamp = self.generate_password()
        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"

        # AccountReference: parent sees this on their M-Pesa prompt.
        # Use admission number if provided (human-readable), else fall back to invoice slice.
        # Safaricom allows up to 12 chars for AccountReference.
        if account_ref:
            # Safaricom AccountReference limit is 12 chars.
            # Compress admission number by removing non-alphanumerics first,
            # then truncate. E.g. "AICS/2026/250" -> "AICS2026250" (11 chars, fits).
            compressed = re.sub(r'[^a-zA-Z0-9]', '', str(account_ref)).upper()
            account_reference = compressed[:12]
        else:
            tenant_prefix = self.school_slug[:4].upper()
            account_reference = f"{tenant_prefix}-{invoice_id[:7]}"
        tx_description = description or f"Fee Payment for {account_reference}"

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": str(int(amount)),
            "PartyA": normalized_phone,
            "PartyB": self.shortcode,
            "PhoneNumber": normalized_phone,
            "CallBackURL": self.callback_url or settings.MPESA.get('CALLBACK_URL'),
            "AccountReference": account_reference,
            "TransactionDesc": tx_description[:50],  # Daraja limit
        }

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            res.raise_for_status()
            data = res.json()

            # Check for Daraja-level errors (ResponseCode != 0)
            response_code = data.get("ResponseCode")
            response_desc = data.get("ResponseDescription", "Unknown error")

            if str(response_code) != "0":
                # Handle specific error cases
                error_msg = response_desc
                if "Invalid Caller Information" in response_desc:
                    error_msg = "M-Pesa configuration error. Please contact support."
                elif "The service request is rejected" in response_desc:
                    error_msg = "Invalid phone number or M-Pesa account not active."
                elif "dsuser has insufficient balance" in response_desc.lower():
                    error_msg = "Insufficient funds in M-Pesa account."

                raise MpesaSTKPushError(f"STK push failed: {error_msg}")

            return data

        except requests.exceptions.Timeout:
            logger.error(f"STK push timeout for tenant {self.school_slug}")
            raise MpesaSTKPushError("M-Pesa is taking too long to respond. Please check your phone and try again.")
        except requests.exceptions.RequestException as e:
            logger.error(f"STK push network error for tenant {self.school_slug}: {str(e)}")
            raise MpesaSTKPushError("Network error connecting to M-Pesa. Please try again.")

    def process_callback(self, callback_data: dict) -> dict:
        """
        Processes incoming Safaricom callback safely.
        Idempotent by checkout_request_id + tenant isolation.
        Uses advisory locks to prevent race conditions with Celery query tasks.
        """
        try:
            stk_callback = callback_data.get("Body", {}).get("stkCallback")
            if not stk_callback:
                return {"status": "error", "reason": "Invalid callback payload structure"}

            checkout_id = stk_callback.get("CheckoutRequestID")
            result_code = stk_callback.get("ResultCode")
            result_desc = stk_callback.get("ResultDesc", "No description")

            if not checkout_id:
                return {"status": "error", "reason": "Missing CheckoutRequestID"}

            # Log every callback attempt for audit trail
            PaymentLog.objects.create(
                tenant=self.tenant,
                checkout_request_id=checkout_id,
                event_type='callback',
                payload=callback_data,
                result_code=str(result_code),
                result_desc=result_desc,
            )

            # Find payment to acquire lock (NO select_related here - fetch plain first)
            payment = (
                Payment.objects
                .filter(tenant=self.tenant, mpesa_checkout_request_id=checkout_id)
                .first()
            )

            if not payment:
                # Orphan callback - payment record not found
                PaymentLog.objects.create(
                    tenant=self.tenant,
                    checkout_request_id=checkout_id,
                    event_type='callback_orphan',
                    payload=callback_data,
                    result_code=str(result_code),
                    result_desc=result_desc,
                )
                logger.error(f"Callback for unknown checkout_id {checkout_id} in tenant {self.school_slug}")
                return {"status": "ignored", "reason": "payment not found for this tenant"}

            # Acquire advisory lock to prevent race with Celery status query
            lock_id = self._payment_lock_id(payment.id)
            with self._advisory_lock(lock_id):
                with transaction.atomic():
                    # Re-fetch with lock inside transaction (NO select_related before select_for_update)
                    payment = (
                        Payment.objects
                        .select_for_update()
                        .get(pk=payment.pk)
                    )

                    # Already processed?
                    if payment.status in ["completed", "confirmed", "COMPLETED", "CONFIRMED"]:
                        logger.info(f"Payment {checkout_id} already processed with status: {payment.status}")
                        receipt_num = None
                        try:
                            receipt_num = payment.receipt.receipt_number
                        except (Receipt.DoesNotExist, AttributeError):
                            pass
                        return {
                            "status": "ignored",
                            "reason": "duplicate callback",
                            "receipt": receipt_num,
                        }

                    # Map result code to status - ALWAYS use string comparison
                    code_str = str(result_code)
                    mapped = self.RESULT_CODE_MAP.get(code_str)

                    if code_str == "0":
                        # Success path
                        metadata_items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
                        items = {item.get("Name"): item.get("Value") for item in metadata_items if "Name" in item}

                        receipt_no = str(items.get("MpesaReceiptNumber", ""))
                        trans_date = items.get("TransactionDate")
                        actual_amount = items.get("Amount")
                        phone_paid_from = items.get("PhoneNumber", "")

                        # Defensive: verify actual paid amount matches requested
                        if actual_amount and float(actual_amount) != float(payment.amount):
                            warning = (
                                f"Amount discrepancy: Expected {payment.amount}, got {actual_amount}. "
                                f"Phone: {phone_paid_from}"
                            )
                            logger.warning(warning)
                            payment.system_notes = warning

                        # Duplicate receipt check (per tenant!)
                        if receipt_no and Payment.objects.filter(
                            tenant=self.tenant,
                            mpesa_receipt_number=receipt_no,
                        ).exclude(pk=payment.pk).exists():
                            payment.status = "failed"
                            payment.failure_reason = "Duplicate M-Pesa receipt detected."
                            payment.notes = payment.failure_reason
                            payment.save()
                            return {"status": "ignored", "reason": "duplicate mpesa receipt"}

                        payment.status = "completed"
                        payment.mpesa_receipt_number = receipt_no
                        payment.mpesa_result_code = str(result_code)
                        payment.notes = result_desc
                        payment.phone_number = phone_paid_from or payment.phone_number
                        payment.mpesa_transaction_date = self._parse_mpesa_date(trans_date)
                        payment.resolved_at = timezone.now()
                        payment.save()

                        # Update student fee balance (lock the fee row)
                        fee = payment.student_fee
                        if fee:
                            fee = StudentFee.objects.select_for_update().get(pk=fee.pk)
                            self._update_fee_status(fee)

                            from .utils import recalculate_student_fees
                            recalculate_student_fees(fee.student)

                        # Triggers downstream ledger distribution
                        if hasattr(payment, 'allocate_to_balances'):
                            payment.allocate_to_balances()

                        receipt = self._create_receipt(payment)
                        return {
                            "status": "success",
                            "receipt": receipt.receipt_number,
                            "amount": str(payment.amount),
                        }

                    # Failure paths
                    if mapped:
                        user_message, status = mapped
                    else:
                        user_message = result_desc or "Transaction failed at Safaricom."
                        status = "failed"

                    payment.status = status.upper() if status in ["completed", "failed", "expired"] else "failed"
                    payment.failure_reason = user_message
                    payment.mpesa_result_code = str(result_code)
                    payment.notes = f"{user_message} (Daraja code: {result_code})"
                    payment.failed_at = timezone.now()
                    payment.resolved_at = timezone.now()
                    payment.save()

                    return {
                        "status": payment.status.lower(),
                        "reason": payment.notes,
                        "result_code": result_code,
                        "user_message": user_message,
                    }

        except Exception as e:
            logger.exception(f"Critical error processing callback for tenant {getattr(self, 'school_slug', 'unknown')}: {str(e)}")
            # Don't raise - return 200 so Safaricom doesn't retry indefinitely
            return {"status": "error", "reason": str(e)}

    def query_transaction_status(self, checkout_request_id: str) -> dict:
        """
        Explicit fallback checking logic against Daraja API for missing/dropped callback events.
        """
        try:
            self._ensure_configured()
        except MpesaConfigurationError:
            logger.error(f"Cannot query status: M-Pesa not configured for tenant {self.school_slug}")
            return {}

        token = self.get_access_token()
        url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
        password, timestamp = self.generate_password()

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=12)
            if response.status_code == 200:
                data = response.json()
                # Log the query
                PaymentLog.objects.create(
                    tenant=self.tenant,
                    checkout_request_id=checkout_request_id,
                    event_type='status_query',
                    payload=data,
                    result_code=str(data.get('ResultCode', '')),
                    result_desc=data.get('ResultDesc', ''),
                )
                return data
            else:
                logger.error(
                    f"Daraja query endpoint returned status {response.status_code} for tenant {self.school_slug}: {response.text}"
                )
                return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying status for CheckoutRequestID {checkout_request_id}: {str(e)}")
            return {}

    def process_status_query_result(self, payment: Payment, query_result: dict) -> Payment:
        """
        Maps Safaricom query status into local database schema.
        Uses advisory locks to prevent race conditions with webhook callbacks.
        """
        if not query_result or "ResultCode" not in query_result:
            logger.warning(f"Invalid query result for Payment ID {payment.id}")
            return payment

        result_code = query_result.get("ResultCode")
        result_desc = query_result.get("ResultDesc", "No status info available.")

        # Acquire advisory lock to prevent race with webhook callback
        lock_id = self._payment_lock_id(payment.id)
        with self._advisory_lock(lock_id):
            with transaction.atomic():
                # Re-fetch with lock (NO select_related before select_for_update)
                payment = Payment.objects.select_for_update().get(pk=payment.id)

                if payment.status.lower() != "pending" :
                    return payment

                code_str = str(result_code)

                if code_str == "0":
                    # Success via query
                    payment.status = "completed"
                    payment.mpesa_result_code = code_str
                    # Generate a synthetic receipt number if we don't have one
                    payment.mpesa_receipt_number = (
                        f"RECON_{payment.mpesa_checkout_request_id[-8:]}".upper()
                    )
                    payment.system_notes = f"Resolved via automated status query. Daraja: {result_desc}"
                    payment.notes = result_desc
                    payment.resolved_at = timezone.now()
                    payment.save()

                    fee = payment.student_fee
                    if fee:
                        fee = StudentFee.objects.select_for_update().get(pk=fee.pk)
                        self._update_fee_status(fee)
                        from .utils import recalculate_student_fees
                        recalculate_student_fees(fee.student)

                    if hasattr(payment, 'allocate_to_balances'):
                        payment.allocate_to_balances()

                    self._create_receipt(payment)

                elif code_str in ["1032", "1037", "2001", "1001"]:
                    mapped = self.RESULT_CODE_MAP.get(code_str, ("Unknown failure", "failed"))
                    payment.status = "failed"
                    payment.mpesa_result_code = code_str
                    payment.failure_reason = f"Daraja Query: {mapped[0]}"
                    payment.notes = payment.failure_reason
                    payment.failed_at = timezone.now()
                    payment.resolved_at = timezone.now()
                    payment.save()
                else:
                    logger.info(f"Payment {payment.mpesa_checkout_request_id} still pending at Safaricom.")

                # Log the query processing
                PaymentLog.objects.create(
                    tenant=payment.tenant,
                    payment=payment,
                    checkout_request_id=payment.mpesa_checkout_request_id,
                    event_type='reconcile',
                    payload=query_result,
                    result_code=code_str,
                    result_desc=result_desc,
                )

                return payment

    def expire_stale_payment(self, payment: Payment) -> Payment:
        """Mark payment as expired if it's been pending too long with no callback."""
        cutoff = timezone.now() - timezone.timedelta(seconds=self.TIMEOUT_SECONDS)
        if payment.status in ["pending", "PENDING"] and payment.created_at <= cutoff:
            # Acquire lock before expiring
            lock_id = self._payment_lock_id(payment.id)
            with self._advisory_lock(lock_id):
                with transaction.atomic():
                    payment = Payment.objects.select_for_update().get(pk=payment.id)
                    if payment.status in ["pending", "PENDING"]:
                        payment.status = "expired"
                        payment.failure_reason = f"STK push timed out. No response from user within {self.TIMEOUT_SECONDS} seconds."
                        payment.notes = payment.failure_reason
                        payment.failed_at = timezone.now()
                        payment.resolved_at = timezone.now()
                        payment.save()

                        PaymentLog.objects.create(
                            tenant=payment.tenant,
                            payment=payment,
                            checkout_request_id=payment.mpesa_checkout_request_id,
                            event_type='expire',
                            result_desc=payment.failure_reason,
                        )
        return payment

    def _parse_mpesa_date(self, value):
        if not value:
            return None
        try:
            parsed = datetime.strptime(str(value), "%Y%m%d%H%M%S")
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        except ValueError:
            logger.warning(f"Could not parse M-Pesa date: {value}")
            return None

    def _create_receipt(self, payment):
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
            payment_method="mpesa",
            term=fee.fee_structure.term if fee else "",
            academic_year=str(fee.fee_structure.academic_year) if fee else "",
            issued_by=payment.recorded_by,
        )

    def _update_fee_status(self, fee):
        total_due = max(
            Decimal("0.00"),
            fee.expected_amount + fee.carried_forward + fee.penalty_amount - fee.waived_amount,
        )
        total_paid = (
            Payment.objects.filter(student_fee=fee, status__in=CONFIRMED_PAYMENT_STATUSES)
            .aggregate(total=Coalesce(Sum("amount"), Value(Decimal("0.00"))))
            .get("total")
            or Decimal("0.00")
        )
        fee.paid_amount = min(total_paid, total_due)
        fee.credit = max(Decimal("0.00"), total_paid - total_due)
        if fee.paid_amount >= total_due:
            fee.status = "paid"
        elif fee.paid_amount > 0:
            fee.status = "partial"
        else:
            fee.status = "unpaid"
        fee.save(update_fields=["paid_amount", "credit", "status", "updated_at"])
        