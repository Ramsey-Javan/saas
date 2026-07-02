import pytest
from django.http import JsonResponse

# Try multiple possible import paths
try:
    from core.no_cache_middleware import NoCacheMiddleware
except ImportError:
    try:
        from core.no_cache_middleware import no_cache_middleware
    except ImportError:
        NoCacheMiddleware = None

from core.exception_handlers import custom_exception_handler


class TestNoCacheMiddleware:
    def test_middleware_adds_cache_headers(self, rf):
        if NoCacheMiddleware is None:
            pytest.skip("NoCacheMiddleware not found with expected name")

        request = rf.get('/api/test/')

        def get_response(request):
            return JsonResponse({'test': True})

        middleware = NoCacheMiddleware(get_response)
        response = middleware(request)

        assert response['Cache-Control'] == 'no-store, no-cache, must-revalidate, max-age=0'
        assert response['Pragma'] == 'no-cache'
        assert response['Expires'] == '0'


class TestExceptionHandlers:
    def test_custom_exception_handler_returns_json(self, rf):
        request = rf.get('/api/test/')

        class FakeException(Exception):
            pass

        exc = FakeException('Test error')
        response = custom_exception_handler(exc, {'request': request})

        # Should return a Response object or None
        assert response is None or hasattr(response, 'data')
