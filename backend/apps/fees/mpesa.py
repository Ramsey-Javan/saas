import base64
import logging
import requests
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)


class MpesaService:
    SANDBOX_BASE_URL = 'https://sandbox.safaricom.co.ke'
    PRODUCTION_BASE_URL = 'https://api.safaricom.co.ke'

    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        self.callback_url = settings.MPESA_CALLBACK_URL
        self.env = settings.MPESA_ENV
        self.base_url = self.SANDBOX_BASE_URL if self.env == 'sandbox' else self.PRODUCTION_BASE_URL

    def get_access_token(self):
        """Fetch OAuth2 access token from Safaricom."""
        url = f'{self.base_url}/oauth/v1/generate?grant_type=client_credentials'
        credentials = base64.b64encode(
            f'{self.consumer_key}:{self.consumer_secret}'.encode()
        ).decode('utf-8')
        headers = {'Authorization': f'Basic {credentials}'}

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json().get('access_token')
        except requests.RequestException as exc:
            logger.error('Failed to get M-Pesa access token: %s', exc)
            raise

    def _get_password_and_timestamp(self):
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        raw = f'{self.shortcode}{self.passkey}{timestamp}'
        password = base64.b64encode(raw.encode()).decode('utf-8')
        return password, timestamp

    def stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """Initiate Lipa Na M-Pesa Online (STK Push)."""
        access_token = self.get_access_token()
        password, timestamp = self._get_password_and_timestamp()

        # Normalize phone: ensure 254XXXXXXXXX format
        phone = str(phone_number).strip().replace('+', '')
        if phone.startswith('0'):
            phone = '254' + phone[1:]

        url = f'{self.base_url}/mpesa/stkpush/v1/processrequest'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': int(amount),
            'PartyA': phone,
            'PartyB': self.shortcode,
            'PhoneNumber': phone,
            'CallBackURL': self.callback_url,
            'AccountReference': account_reference[:12],
            'TransactionDesc': transaction_desc[:13],
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.error('STK Push failed for %s: %s', phone_number, exc)
            raise

    def stk_push_query(self, checkout_request_id):
        """Query the status of an STK Push request."""
        access_token = self.get_access_token()
        password, timestamp = self._get_password_and_timestamp()

        url = f'{self.base_url}/mpesa/stkpushquery/v1/query'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'CheckoutRequestID': checkout_request_id,
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.error('STK Push query failed for %s: %s', checkout_request_id, exc)
            raise
