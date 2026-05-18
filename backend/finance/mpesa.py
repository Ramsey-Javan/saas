# backend/finance/mpesa.py
import base64
from decimal import Decimal
from datetime import datetime

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import CONFIRMED_PAYMENT_STATUSES, Payment, Receipt


class MpesaService:
    def __init__(self, env=None):
        mpesa_settings = getattr(settings, 'MPESA', {})
        self.env = env or mpesa_settings.get('ENV', 'sandbox')
        self.consumer_key = mpesa_settings.get('CONSUMER_KEY', '')
        self.consumer_secret = mpesa_settings.get('CONSUMER_SECRET', '')
        self.shortcode = mpesa_settings.get('SHORTCODE', '')
        self.passkey = mpesa_settings.get('PASSKEY', '')
        self.callback_url = mpesa_settings.get('CALLBACK_URL', '')
        self.base_url = (
            "https://sandbox.safaricom.co.ke"
            if self.env == "sandbox"
            else "https://api.safaricom.co.ke"
        )
        self._access_token = None

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
                'MPESA_CALLBACK_URL': self.callback_url,
            }.items()
            if self._is_placeholder(value)
        ]
        if missing:
            raise ValueError(f'Missing M-Pesa configuration: {", ".join(missing)}')

    def get_access_token(self):
        self._ensure_configured()
        if self._access_token:
            return self._access_token
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        res = requests.get(url, auth=(self.consumer_key, self.consumer_secret), timeout=10)
        res.raise_for_status()
        self._access_token = res.json()["access_token"]
        return self._access_token

    def generate_password(self):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        raw = f"{self.shortcode}{self.passkey}{timestamp}"
        return base64.b64encode(raw.encode()).decode("utf-8"), timestamp

    def initiate_stk_push(self, phone, amount, account_ref, description):
        token = self.get_access_token()
        password, timestamp = self.generate_password()
        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": str(int(amount)),  # Daraja expects string integer
            "PartyA": phone,
            "PartyB": self.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": self.callback_url,
            "AccountReference": account_ref,
            "TransactionDesc": description,
        }
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        res.raise_for_status()
        return res.json()

    def process_callback(self, body):
        """Handles Daraja callback. Idempotent by checkout_request_id."""
        try:
            result = body.get("Body", {}).get("stkCallback")
            if not result:
                return {"status": "error", "reason": "Invalid callback payload"}

            checkout_id = result["CheckoutRequestID"]
            result_code = int(result["ResultCode"])
            result_desc = result["ResultDesc"]

            with transaction.atomic():
                payment = (
                    Payment.objects
                    .select_related("student_fee", "student_fee__fee_structure")
                    .filter(mpesa_checkout_request_id=checkout_id)
                    .select_for_update(of=("self",))
                    .first()
                )
                if not payment:
                    return {"status": "ignored", "reason": "payment not found"}

                if payment.status == "completed":
                    return {
                        "status": "ignored",
                        "reason": "duplicate callback",
                        "receipt": getattr(getattr(payment, "receipt", None), "receipt_number", None),
                    }

                if result_code == 0:
                    callback_metadata = result.get("CallbackMetadata", {}).get("Item", [])
                    items = {item.get("Name"): item.get("Value") for item in callback_metadata}
                    receipt_no = str(items.get("MpesaReceiptNumber", ""))
                    trans_date = items.get("TransactionDate")

                    if receipt_no and Payment.objects.filter(mpesa_receipt_number=receipt_no).exclude(pk=payment.pk).exists():
                        return {"status": "ignored", "reason": "duplicate mpesa receipt"}

                    payment.status = "completed"
                    payment.mpesa_receipt_number = receipt_no
                    payment.notes = result_desc
                    payment.mpesa_transaction_date = self._parse_mpesa_date(trans_date)
                    payment.save(update_fields=[
                        "status",
                        "mpesa_receipt_number",
                        "mpesa_transaction_date",
                        "notes",
                    ])

                    fee = payment.student_fee
                    if fee:
                        fee.paid_amount = fee.paid_amount + payment.amount
                        self._update_fee_status(fee)

                    receipt = self._create_receipt(payment)
                    return {"status": "success", "receipt": receipt.receipt_number}

                payment.status = "expired" if result_code in {1032, 1037} else "failed"
                payment.notes = result_desc
                payment.save(update_fields=["status", "notes"])
                return {"status": payment.status, "reason": result_desc}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def expire_stale_payment(self, payment):
        cutoff = timezone.now() - timezone.timedelta(minutes=5)
        if payment.status == "pending" and payment.created_at <= cutoff:
            payment.status = "expired"
            payment.notes = "STK push expired before confirmation."
            payment.save(update_fields=["status", "notes"])
        return payment

    def _parse_mpesa_date(self, value):
        if not value:
            return None
        parsed = datetime.strptime(str(value), "%Y%m%d%H%M%S")
        return timezone.make_aware(parsed, timezone.get_current_timezone())

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
            academic_year=fee.fee_structure.academic_year if fee else "",
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
