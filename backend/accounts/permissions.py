from rest_framework import permissions

class IsSchoolAdmin(permissions.BasePermission):
    """Allow access only to admin/superadmin roles."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.role in ['admin', 'superadmin']
        )

class IsTeacher(permissions.BasePermission):
    """Allow access only to teachers and admins."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.role in ['teacher', 'admin', 'superadmin']
        )

class IsBursar(permissions.BasePermission):
    """Allow access only to bursars and admins."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.role in ['bursar', 'admin', 'superadmin']
        )

class IsParent(permissions.BasePermission):
    """Allow access only to parents viewing their own children."""
    def has_object_permission(self, request, view, obj):
        # Parents can only view their own linked students
        if request.user.is_authenticated and getattr(request.user, 'role', None) == 'parent':
            return bool(obj.primary_guardian and obj.primary_guardian.user == request.user)
        return request.user.is_authenticated