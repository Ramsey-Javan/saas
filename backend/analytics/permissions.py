"""Permission classes enforcing the analytics permission matrix.

Each class resolves the relevant object (exam/classroom/student/subject)
from query params ONCE and stashes it on `request`, so views.py doesn't
have to re-fetch it.
"""
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import ValidationError, NotFound

from academics.models import ExamSetup, ExamSubject, ClassSubjectAssignment, Subject
from academics.permissions import user_owns_student
from academics.views.mixins import _is_admin, _is_teacher, _is_parent
from students.models import Classroom, Student


def _authed(request):
    return bool(request.user and request.user.is_authenticated and getattr(request.user, 'tenant', None))


def _resolve_exam(request):
    if hasattr(request, '_analytics_exam'):
        return request._analytics_exam
    exam_id = request.query_params.get('exam_id')
    if not exam_id:
        raise ValidationError({'exam_id': 'This field is required.'})
    exam = ExamSetup.objects.select_related('classroom').filter(
        id=exam_id, tenant=request.user.tenant,
    ).first()
    if not exam:
        raise NotFound('Exam not found.')
    request._analytics_exam = exam
    return exam


def _resolve_classroom(request, param='classroom_id'):
    attr = f'_analytics_classroom_{param}'
    if hasattr(request, attr):
        return getattr(request, attr)
    classroom_id = request.query_params.get(param)
    if not classroom_id:
        raise ValidationError({param: 'This field is required.'})
    classroom = Classroom.objects.filter(id=classroom_id, tenant=request.user.tenant).first()
    if not classroom:
        raise NotFound('Classroom not found.')
    setattr(request, attr, classroom)
    return classroom


def _resolve_student(request):
    if hasattr(request, '_analytics_student'):
        return request._analytics_student
    student_id = request.query_params.get('student_id')
    if not student_id:
        raise ValidationError({'student_id': 'This field is required.'})
    student = Student.objects.filter(id=student_id, tenant=request.user.tenant).select_related(
        'primary_guardian', 'classroom',
    ).first()
    if not student:
        raise NotFound('Student not found.')
    request._analytics_student = student
    return student


def _resolve_subject(request):
    if hasattr(request, '_analytics_subject'):
        return request._analytics_subject
    subject_id = request.query_params.get('subject_id')
    if not subject_id:
        raise ValidationError({'subject_id': 'This field is required.'})
    subject = Subject.objects.filter(id=subject_id, tenant=request.user.tenant).first()
    if not subject:
        raise NotFound('Subject not found.')
    request._analytics_subject = subject
    return subject


def _teacher_is_class_teacher(user, classroom):
    return classroom is not None and classroom.class_teacher_id == user.id


def _teacher_assigned_subject_ids_for_exam(user, exam):
    direct = set(ExamSubject.objects.filter(exam=exam, teacher=user).values_list('subject_id', flat=True))
    via_assignment = set(ClassSubjectAssignment.objects.filter(
        tenant=user.tenant, teacher=user, classroom=exam.classroom,
        academic_year=exam.academic_year, term=exam.term,
    ).values_list('subject_id', flat=True))
    return direct | via_assignment


class IsAdminOnly(BasePermission):
    """school-overview, subject-school-analysis: admin/superadmin only."""
    def has_permission(self, request, view):
        return _authed(request) and _is_admin(request.user)


class CanViewTermSummary(BasePermission):
    """term-summary: admin sees the whole school; teachers may view too
    (the view itself narrows what they see). Parents never."""
    def has_permission(self, request, view):
        if not _authed(request):
            return False
        return _is_admin(request.user) or _is_teacher(request.user)


class CanViewExamBreakdown(BasePermission):
    """exam-breakdown: admin sees everything; class teacher of THIS exam's
    classroom sees it in full; a subject teacher only if assigned to at
    least one subject in this exam. Parents never."""
    def has_permission(self, request, view):
        if not _authed(request):
            return False
        if _is_admin(request.user):
            return True
        if not _is_teacher(request.user):
            return False
        exam = _resolve_exam(request)
        if _teacher_is_class_teacher(request.user, exam.classroom):
            return True
        return len(_teacher_assigned_subject_ids_for_exam(request.user, exam)) > 0


class CanViewClassRankings(BasePermission):
    """class-rankings (exam-scoped): admin sees everything; ONLY the class
    teacher of that specific classroom. Parents never."""
    def has_permission(self, request, view):
        if not _authed(request):
            return False
        if _is_admin(request.user):
            return True
        if not _is_teacher(request.user):
            return False
        exam = _resolve_exam(request)
        return _teacher_is_class_teacher(request.user, exam.classroom)


class CanViewSubjectAnalysis(BasePermission):
    """subject-analysis (exam-scoped): same shape as exam-breakdown."""
    def has_permission(self, request, view):
        if not _authed(request):
            return False
        if _is_admin(request.user):
            return True
        if not _is_teacher(request.user):
            return False
        exam = _resolve_exam(request)
        if _teacher_is_class_teacher(request.user, exam.classroom):
            return True
        return len(_teacher_assigned_subject_ids_for_exam(request.user, exam)) > 0


class CanViewClassroomTermData(BasePermission):
    """class-performance, class-ranking, grade-distribution,
    subject-comparison (all classroom+term scoped): admin sees
    everything; ONLY the class teacher of that specific classroom sees
    it. Parents never."""
    def has_permission(self, request, view):
        if not _authed(request):
            return False
        classroom = _resolve_classroom(request)
        if _is_admin(request.user):
            return True
        if not _is_teacher(request.user):
            return False
        return _teacher_is_class_teacher(request.user, classroom)


class CanViewCohortReference(BasePermission):
    """cohort-reference: needed by StudentProfilePage for ANY viewer of
    that page -- admin, the class teacher, or a parent viewing their own
    child's profile."""
    def has_permission(self, request, view):
        if not _authed(request):
            return False
        classroom = _resolve_classroom(request)
        if _is_admin(request.user):
            return True
        if _is_teacher(request.user):
            return _teacher_is_class_teacher(request.user, classroom)
        if _is_parent(request.user):
            return Student.objects.filter(
                tenant=request.user.tenant, classroom=classroom,
            ).filter(
                primary_guardian__user=request.user,
            ).exists()
        return False


class CanViewStudentProfile(BasePermission):
    """student-profile / student-report-card / student-performance /
    student-longitudinal: admin sees everyone; a class teacher sees only
    students in their own classroom; a parent sees only their own child."""
    def has_permission(self, request, view):
        if not _authed(request):
            return False
        if _is_admin(request.user):
            return True
        student = _resolve_student(request)
        if _is_teacher(request.user):
            return (
                student.classroom is not None
                and _teacher_is_class_teacher(request.user, student.classroom)
            )
        if _is_parent(request.user):
            return user_owns_student(request.user, student)
        return False


class CanViewImprovementTracker(BasePermission):
    """improvement-tracker: admin sees everything; only the class teacher
    of that specific classroom. No subject teachers, no parents."""
    def has_permission(self, request, view):
        if not _authed(request):
            return False
        classroom = _resolve_classroom(request)
        if _is_admin(request.user):
            return True
        if not _is_teacher(request.user):
            return False
        return _teacher_is_class_teacher(request.user, classroom)


class CanViewEarlyWarning(BasePermission):
    """early-warning: admin sees the whole school; class teachers and
    subject teachers may view too (views.py scopes the result down)."""
    def has_permission(self, request, view):
        if not _authed(request):
            return False
        if _is_admin(request.user):
            return True
        if not _is_teacher(request.user):
            return False
        # Allow any teacher — the view narrows the data set appropriately
        return True


class CanViewSubjectTeacherSummary(BasePermission):
    """subject-teacher-summary: subject teachers see their own subjects'
    analytics; class teachers and admins see this too (but the view
    will redirect them to their more appropriate dashboards)."""
    def has_permission(self, request, view):
        if not _authed(request):
            return False
        if _is_admin(request.user):
            return True
        if not _is_teacher(request.user):
            return False
        return True