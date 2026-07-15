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

from rest_framework import permissions


class TenantAwarePermission(permissions.BasePermission):
    """
    Ensures every request is scoped to a single active tenant.
    Falls back to request.user.tenant if request.tenant is not set by middleware.
    """

    def _get_tenant(self, request):
        # Priority 1: tenant set by middleware (TenantScopedMixin or custom middleware)
        tenant = getattr(request, 'tenant', None)
        if tenant is not None:
            return tenant
        # Priority 2: tenant from user's profile
        tenant = getattr(request.user, 'tenant', None)
        if tenant is not None:
            # Set it on request for downstream use
            request.tenant = tenant
            return tenant
        return None

    def has_permission(self, request, view):
        tenant = self._get_tenant(request)
        if tenant is None:
            return False
        # Check tenant is active
        if hasattr(tenant, 'is_active') and not tenant.is_active:
            return False
        # Ensure user belongs to this tenant (unless superuser)
        if not request.user.is_superuser:
            user_tenant = getattr(request.user, 'tenant', None)
            if user_tenant and user_tenant.id != tenant.id:
                return False
        return True

    def has_object_permission(self, request, view, obj):
        tenant = self._get_tenant(request)
        if tenant is None:
            return False
        
        # Direct tenant match
        if hasattr(obj, 'tenant'):
            return obj.tenant == tenant
        # Nested relations
        if hasattr(obj, 'student') and hasattr(obj.student, 'tenant'):
            return obj.student.tenant == tenant
        if hasattr(obj, 'payment') and hasattr(obj.payment, 'tenant'):
            return obj.payment.tenant == tenant
        if hasattr(obj, 'fee_structure') and hasattr(obj.fee_structure, 'tenant'):
            return obj.fee_structure.tenant == tenant
        return True


class IsAdminOrBursar(permissions.BasePermission):
    """
    Allows access only to admin or bursar users.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        role = getattr(request.user, 'role', '').lower()
        return role in ('admin', 'bursar', 'headteacher', 'principal')


class IsAdminBursarOrOwnParent(permissions.BasePermission):
    """
    Allows access to admin/bursar, or the parent of the student in question.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        role = getattr(request.user, 'role', '').lower()
        if role in ('admin', 'bursar', 'headteacher', 'principal'):
            return True
        # Parents can only access their own children's data
        # Object-level check happens in has_object_permission
        return role == 'parent'

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        role = getattr(request.user, 'role', '').lower()
        if role in ('admin', 'bursar', 'headteacher', 'principal'):
            return True
        if role == 'parent':
            # Check if this parent is the primary guardian of the student
            student = getattr(obj, 'student', None)
            if student:
                guardian = getattr(student, 'primary_guardian', None)
                if guardian and hasattr(guardian, 'user'):
                    return guardian.user == request.user
        return False