"""
This module provides structured, user-friendly error responses for all API errors.
No raw 500 Internal Server Error should ever reach the client without a
structured message.
"""
import logging
from http import HTTPStatus

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied as DjangoPermissionDenied
from django.http import JsonResponse
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied as DRFPermissionDenied,
    ValidationError,
)
from rest_framework.response import Response

logger = logging.getLogger(__name__)


# ── NEW: Middleware that forces JSON for API errors (404, 500, 403) ──
class JSONErrorMiddleware:
    """
    Intercepts Django's default HTML error responses (404, 500, 403)
    and returns JSON when the request path starts with /api/.
    This runs BEFORE DRF's exception handler sees anything.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.status_code_description = {
            v.value: v.phrase for v in HTTPStatus
        }

    def __call__(self, request):
        response = self.get_response(request)

        # Only intercept API routes
        if not request.path.startswith('/api/'):
            return response

        # Only intercept actual error status codes
        if response.status_code < 400:
            return response

        # If it's already JSON, don't touch it
        content_type = response.get('Content-Type', '')
        if 'application/json' in content_type:
            return response

        # Force JSON error response
        code = response.status_code
        message = getattr(response, 'reason_phrase', self.status_code_description.get(code, 'Error'))

        # Try to extract any existing message from Django's response
        try:
            # Django's debug page or default error page — don't leak HTML
            detail = message
        except Exception:
            detail = 'An error occurred.'

        data = {
            "error": {
                "code": f"http_{code}",
                "message": message,
                "details": {"url": request.get_full_path()}
            }
        }

        json_response = JsonResponse(data, status=code)
        json_response['Content-Type'] = 'application/json'
        return json_response
# ── END NEW ──


def custom_exception_handler(exc, context):
    """Custom exception handler that returns structured JSON for all errors.
    Usage in settings.py:
         REST_FRAMEWORK = {
             'EXCEPTION_HANDLER': 'core.exception_handlers.custom_exception_handler',
         }
    """
    # Handle custom AnalyticsError first (it already has structured detail)
    try:
        # Fixed import path to match your actual file structure
        from analytics.services.exceptions import AnalyticsError
        if isinstance(exc, AnalyticsError):
            # Uses your custom to_response_data() method instead of non-existent exc.detail
            return Response(exc.to_response_data(), status=status.HTTP_400_BAD_REQUEST)
    except ImportError:
        # Fallback if analytics module is not present in this project environment
        pass

    # SECURITY FIX #18: Handle M-Pesa specific exceptions with proper error codes
    try:
        from finance.mpesa import MpesaSTKPushError, MpesaConfigurationError
        if isinstance(exc, MpesaConfigurationError):
            logger.error(f"M-Pesa configuration error: {str(exc)}")
            return Response({
                "error": {
                    "code": "mpesa_not_configured",
                    "message": "M-Pesa is not configured for this school. Please contact support.",
                    "details": {}
                }
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if isinstance(exc, MpesaSTKPushError):
            logger.error(f"M-Pesa STK push error: {str(exc)}")
            return Response({
                "error": {
                    "code": "mpesa_stk_failed",
                    "message": str(exc),
                    "details": {}
                }
            }, status=status.HTTP_502_BAD_GATEWAY)
    except ImportError:
        # finance.mpesa may not be available in all environments
        pass

    # DRF ValidationError — field-level errors
    if isinstance(exc, ValidationError):
        return Response({
            "error": {
                "code": "validation_error",
                "message": "Please correct the errors below.",
                "details": {"fields": exc.detail}
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    # DRF Authentication errors
    if isinstance(exc, NotAuthenticated):
        return Response({
            "error": {
                "code": "not_authenticated",
                "message": "Authentication credentials were not provided.",
                "details": {}
            }
        }, status=status.HTTP_401_UNAUTHORIZED)

    if isinstance(exc, AuthenticationFailed):
        return Response({
            "error": {
                "code": "authentication_failed",
                "message": str(exc.detail) if hasattr(exc, 'detail') else "Authentication failed.",
                "details": {}
            }
        }, status=status.HTTP_401_UNAUTHORIZED)

    # DRF / Django Permission Denied
    if isinstance(exc, (DRFPermissionDenied, DjangoPermissionDenied)):
        return Response({
            "error": {
                "code": "permission_denied",
                "message": "You do not have permission to perform this action.",
                "details": {}
            }
        }, status=status.HTTP_403_FORBIDDEN)

    # Object not found
    if isinstance(exc, ObjectDoesNotExist):
        return Response({
            "error": {
                "code": "not_found",
                "message": "The requested resource was not found.",
                "details": {}
            }
        }, status=status.HTTP_404_NOT_FOUND)

    # Generic DRF APIException (handles any other standard DRF exceptions like MethodNotAllowed, ParseError, etc.)
    if isinstance(exc, APIException):
        # Dynamically build a slug-like code from the class name (e.g., MethodNotAllowed -> method_not_allowed)
        class_name = exc.__class__.__name__
        error_code = "".join(["_" + c.lower() if c.isupper() else c for c in class_name]).lstrip("_")
        return Response({
            "error": {
                "code": error_code,
                "message": str(exc.detail) if hasattr(exc, 'detail') else "An API error occurred.",
                "details": {}
            }
        }, status=getattr(exc, 'status_code', status.HTTP_400_BAD_REQUEST))

    # Catch-all for truly unexpected errors — log full traceback, return safe message
    logger.exception("Unhandled exception in API endpoint")
    return Response({
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred. Our team has been notified and is working on it.",
            "details": {}
        }
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)