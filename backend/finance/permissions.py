from rest_framework import permissions


class IsAdminOrBursar(permissions.BasePermission):
    """Allow access only to admin/superadmin/bursar roles."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ('superadmin', 'admin', 'bursar')
        )


class IsAdminBursarOrOwnParent(permissions.BasePermission):
    """Allow admins/bursars or the student's own parent."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ('superadmin', 'admin', 'bursar', 'parent')
        )

    def has_object_permission(self, request, view, obj):
        if request.user.role in ('superadmin', 'admin', 'bursar'):
            return True
        if request.user.role == 'parent':
            return bool(
                getattr(obj, 'primary_guardian', None)
                and getattr(obj.primary_guardian, 'user', None) == request.user
            )
        return False
