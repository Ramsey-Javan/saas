from rest_framework import permissions

class IsSuperAdmin(permissions.BasePermission):
    """Allow access only to platform superadmins (tenant=None)."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'superadmin'
        )


class IsSchoolAdmin(permissions.BasePermission):
    """Allow access only to school admins who belong to a specific tenant."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'admin'
            and request.user.tenant is not None
        )

class IsTeacher(permissions.BasePermission):
    """Allow access only to teachers belonging to a school."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'teacher'
            and request.user.tenant is not None
        )

class IsBursar(permissions.BasePermission):
    """Allow access only to bursars belonging to a school."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'bursar'
            and request.user.tenant is not None
        )


class IsParent(permissions.BasePermission):
    """Allow access only to parents viewing their own children."""
    def has_object_permission(self, request, view, obj):
        if (
            request.user.is_authenticated
            and getattr(request.user, 'role', None) == 'parent'
            and request.user.tenant is not None
        ):
            return bool(
                obj.primary_guardian
                and obj.primary_guardian.user == request.user
            )
        return False