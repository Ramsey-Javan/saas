"""
Ensures no tenant-scoped (or session-scoped) API response can ever be
served from a shared cache to a different session.

Root cause this fixes: DRF sends no Cache-Control headers by default, and
two tenants/sessions hitting the *same* URL (e.g. localhost dev with no
subdomain routing) differ only in their Authorization header. Browsers are
not guaranteed to treat differing Authorization headers as cache-distinct
unless told to via Vary, so a GET response can be replayed from disk/memory
cache to a different logged-in user. This middleware closes that gap at
the source rather than relying on per-view opt-in.
"""


class NoCacheAPIMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            existing_vary = response.get('Vary', '')
            vary_parts = {part.strip() for part in existing_vary.split(',') if part.strip()}
            vary_parts.add('Authorization')
            response['Vary'] = ', '.join(sorted(vary_parts))

        return response