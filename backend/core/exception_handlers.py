from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Wrap every DRF error response into a consistent shape.
    """
    response = exception_handler(exc, context)

    if response is None:
        return Response({
            'error': True,
            'message': 'An unexpected error occurred.',
            'details': None,
            'status_code': 500,
        }, status=500)

    data = response.data
    message = 'An error occurred.'
    details = None

    if isinstance(data, dict):
        if 'detail' in data:
            message = str(data['detail'])
        else:
            details = data
            first_key = next(iter(data), None)
            if first_key:
                first_val = data[first_key]
                if isinstance(first_val, list) and first_val:
                    message = f"{first_key}: {first_val[0]}"
                else:
                    message = str(first_val)
    elif isinstance(data, list) and data:
        message = str(data[0])

    response.data = {
        'error': True,
        'message': message,
        'details': details,
        'status_code': response.status_code,
    }
    return response