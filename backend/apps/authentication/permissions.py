from rest_framework import permissions


class IsAdminRole(permissions.BasePermission):
    """Allow access only to users with the 'admin' role."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin())


class IsTeacherOrAdmin(permissions.BasePermission):
    """Allow access to teachers and admins."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ('admin', 'teacher') or request.user.is_superuser


class IsAccountantOrAdmin(permissions.BasePermission):
    """Allow access to accountants and admins."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ('admin', 'accountant') or request.user.is_superuser


class IsParentOrAdmin(permissions.BasePermission):
    """Allow access to parents and admins."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ('admin', 'parent') or request.user.is_superuser


class IsOwnerOrAdmin(permissions.BasePermission):
    """Allow object access only to the owner or an admin."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_admin():
            return True
        return obj == request.user or getattr(obj, 'user', None) == request.user


class ReadOnly(permissions.BasePermission):
    """Allow read-only access."""

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS
