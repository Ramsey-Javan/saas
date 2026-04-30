import base64
from datetime import datetime

import requests
from django.conf import settings


class MpesaService:
    """Small Daraja API wrapper for STK Push and callback normalization."""

    SANDBOX_BASE = 'https://sandbox.safaricom.co.ke'
    PROD_BASE = 'https://api.safaricom.co.ke'

    def __init__(self):
        cfg = settings.MPESA
        self.consumer_key = cfg.get('CONSUMER_KEY', '')
        self.consumer_secret = cfg.get('CONSUMER_SECRET', '')
        self.shortcode = cfg.get('SHORTCODE', '')
        self.passkey = cfg.get('PASSKEY', '')
        self.callback_url = cfg.get('CALLBACK_URL', '')
        self.base_url = self.SANDBOX_BASE if cfg.get('ENV') == 'sandbox' else self.PROD_BASE

    def _get_access_token(self):
        url = f'{self.base_url}/oauth/v1/generate?grant_type=client_credentials'
        response = requests.get(url, auth=(self.consumer_key, self.consumer_secret), timeout=30)
        response.raise_for_status()
        return response.json()['access_token']

    def _get_password(self):
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        raw = f'{self.shortcode}{self.passkey}{timestamp}'
        return base64.b64encode(raw.encode()).decode(), timestamp

    def stk_push(self, phone: str, amount: int, account_ref: str, description: str) -> dict:
        token = self._get_access_token()
        password, timestamp = self._get_password()
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': amount,
            'PartyA': phone,
            'PartyB': self.shortcode,
            'PhoneNumber': phone,
            'CallBackURL': self.callback_url,
            'AccountReference': account_ref,
            'TransactionDesc': description,
        }

        response = requests.post(
            f'{self.base_url}/mpesa/stkpush/v1/processrequest',
            json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def process_callback(self, callback_data: dict) -> dict:
        stk = callback_data.get('Body', {}).get('stkCallback', {})
        result_code = stk.get('ResultCode')
        result = {
            'checkout_request_id': stk.get('CheckoutRequestID', ''),
            'merchant_request_id': stk.get('MerchantRequestID', ''),
            'result_code': result_code,
            'result_desc': stk.get('ResultDesc', ''),
            'success': result_code == 0,
            'mpesa_receipt_number': '',
            'phone': '',
            'amount': 0,
        }

        if result_code == 0:
            items = {
                item['Name']: item.get('Value')
                for item in stk.get('CallbackMetadata', {}).get('Item', [])
            }
            result['mpesa_receipt_number'] = items.get('MpesaReceiptNumber', '')
            result['phone'] = str(items.get('PhoneNumber', ''))
            result['amount'] = items.get('Amount', 0)

        return result
