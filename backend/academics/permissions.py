from rest_framework.permissions import BasePermission


def _is_authenticated_with_role(request):
    return bool(request.user and request.user.is_authenticated and getattr(request.user, 'role', None))


def _is_parent_role(user):
    return getattr(user, 'role', None) in ('parent', 'guardian')


def user_owns_student(user, student):
    guardian = getattr(student, 'primary_guardian', None)
    return bool(guardian and getattr(guardian, 'user_id', None) == user.id)


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return _is_authenticated_with_role(request) and request.user.role in ('admin', 'superadmin')


class IsTeacherOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return _is_authenticated_with_role(request) and request.user.role in ('admin', 'superadmin', 'teacher')


class IsTeacherOrAdminReadOnly(BasePermission):
    def has_permission(self, request, view):
        return _is_authenticated_with_role(request) and request.user.role in ('admin', 'superadmin', 'teacher')


class CanViewTimetable(BasePermission):
    def has_permission(self, request, view):
        return _is_authenticated_with_role(request) and request.user.role in (
            'admin', 'superadmin', 'teacher', 'parent', 'guardian'
        )


class CanViewReportCard(BasePermission):
    def has_permission(self, request, view):
        return _is_authenticated_with_role(request) and request.user.role in (
            'admin', 'superadmin', 'teacher', 'parent', 'guardian'
        )

    def has_object_permission(self, request, view, obj):
        if request.user.role in ('admin', 'superadmin', 'teacher'):
            return True
        if _is_parent_role(request.user):
            return obj.status == 'published' and user_owns_student(request.user, obj.student)
        return False


class CanViewExamResult(BasePermission):
    def has_permission(self, request, view):
        return _is_authenticated_with_role(request) and request.user.role in (
            'admin', 'superadmin', 'teacher', 'parent', 'guardian'
        )

    def has_object_permission(self, request, view, obj):
        if request.user.role in ('admin', 'superadmin', 'teacher'):
            return True
        student = getattr(obj, 'student', None) or getattr(getattr(obj, 'candidate', None), 'student', None)
        if _is_parent_role(request.user) and student:
            return user_owns_student(request.user, student)
        return False
