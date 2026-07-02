"""
Reusable mocks for every external service.
NEVER let a test hit a real API.
"""


class MockMpesaSuccessResponse:
    @staticmethod
    def stk_push():
        return {
            'MerchantRequestID': 'test-merchant-123',
            'CheckoutRequestID': 'ws_CO_test_123',
            'ResponseCode': '0',
            'ResponseDescription': 'Success',
            'CustomerMessage': 'Success',
        }

    @staticmethod
    def callback_success(checkout_id, amount, phone):
        return {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'test-merchant-123',
                    'CheckoutRequestID': checkout_id,
                    'ResultCode': 0,
                    'ResultDesc': 'Success',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': amount},
                            {'Name': 'MpesaReceiptNumber', 'Value': 'QKA12BNZ4R'},
                            {'Name': 'PhoneNumber', 'Value': phone},
                        ]
                    },
                }
            }
        }

    @staticmethod
    def callback_failure(checkout_id):
        return {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'test-merchant-123',
                    'CheckoutRequestID': checkout_id,
                    'ResultCode': 1032,
                    'ResultDesc': 'Request cancelled by user',
                }
            }
        }


class MockSMSResponse:
    @staticmethod
    def success():
        return {
            'SMSMessageData': {
                'Recipients': [
                    {
                        'messageId': 'ATXid_test123',
                        'cost': 'KES 0.8000',
                        'status': 'Success',
                    }
                ]
            }
        }


class MockWhatsAppResponse:
    @staticmethod
    def success():
        class FakeMessage:
            sid = 'SMtest1234567890'
            status = 'sent'

        return FakeMessage()