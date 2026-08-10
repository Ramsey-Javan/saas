from rest_framework.permissions import BasePermission, SAFE_METHODS


def is_admin(user):
    return getattr(user, 'role', None) in ('admin', 'superadmin')


def is_teacher(user):
    return getattr(user, 'role', None) == 'teacher'


def is_parent(user):
    return getattr(user, 'role', None) in ('parent', 'guardian')


class IsTimetableAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return getattr(request.user, 'role', None) in ('admin', 'superadmin', 'teacher', 'parent', 'guardian')
        return is_admin(request.user)


class IsTimetableAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_admin(request.user))

