from django.core.exceptions import PermissionDenied


class TenantScopedMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = getattr(self.request.user, 'tenant', None)
        if tenant:
            return queryset.filter(tenant=tenant)
        if getattr(self.request.user, 'is_superuser', False):
            return queryset
        return queryset.none()

    def perform_create(self, serializer):
        tenant = getattr(self.request.user, 'tenant', None)
        if not tenant and not getattr(self.request.user, 'is_superuser', False):
            raise PermissionDenied('Timetable records must be created under a school tenant.')
        serializer.save(tenant=tenant)

