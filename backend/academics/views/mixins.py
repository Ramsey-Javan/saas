"""Shared mixins and permission helpers for academics views."""
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError

from students.models import Student

from ..models import ClassSubjectAssignment
from ..permissions import user_owns_student


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
            raise PermissionDenied('Academics records must be created under a school tenant.')
        serializer.save(tenant=tenant)


def _teacher_classroom_ids(user):
    return ClassSubjectAssignment.objects.filter(tenant=user.tenant, teacher=user).values_list('classroom_id', flat=True)


def _teacher_subject_ids(user):
    return ClassSubjectAssignment.objects.filter(tenant=user.tenant, teacher=user).values_list('subject_id', flat=True)


def _is_admin(user):
    return getattr(user, 'role', None) in ('admin', 'superadmin')


def _is_teacher(user):
    return getattr(user, 'role', None) == 'teacher'


def _is_parent(user):
    return getattr(user, 'role', None) in ('parent', 'guardian')


def _validate_student_for_user(user, student_id):
    student = Student.objects.filter(id=student_id, tenant=user.tenant).select_related('primary_guardian').first()
    if not student:
        raise ValidationError({'student': 'Student not found in this school.'})
    if _is_teacher(user) and student.classroom_id not in set(_teacher_classroom_ids(user)):
        raise PermissionDenied('You can only access students in your assigned classes.')
    if _is_parent(user) and not user_owns_student(user, student):
        raise PermissionDenied('You can only access your own child.')
    return student
