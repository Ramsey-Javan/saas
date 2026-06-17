"""Academics views package — re-exports all viewsets for backwards compatibility."""
from .curriculum import (
    ClassSubjectAssignmentViewSet,
    LearningOutcomeViewSet,
    StrandViewSet,
    SubjectViewSet,
    SubStrandViewSet,
)
from .exams import ExamResultViewSet, ExamSetupViewSet
from .grades import CBCGradeViewSet, ExamConfigViewSet
from .mixins import (
    TenantScopedMixin,
    _is_admin,
    _is_parent,
    _is_teacher,
    _teacher_classroom_ids,
    _teacher_subject_ids,
    _validate_student_for_user,
)
from .national_exams import (
    NationalExamCandidateViewSet,
    NationalExamResultViewSet,
    NationalExamSessionViewSet,
)
from .school_life import (
    AttendanceSessionViewSet,
    ClassTimetableViewSet,
    CoCurricularActivityViewSet,
    ReportCardViewSet,
    StudentCoCurricularViewSet,
)

__all__ = [
    'AttendanceSessionViewSet',
    'CBCGradeViewSet',
    'ClassSubjectAssignmentViewSet',
    'ClassTimetableViewSet',
    'CoCurricularActivityViewSet',
    'ExamConfigViewSet',
    'ExamResultViewSet',
    'ExamSetupViewSet',
    'LearningOutcomeViewSet',
    'NationalExamCandidateViewSet',
    'NationalExamResultViewSet',
    'NationalExamSessionViewSet',
    'ReportCardViewSet',
    'StrandViewSet',
    'StudentCoCurricularViewSet',
    'SubjectViewSet',
    'SubStrandViewSet',
    'TenantScopedMixin',
    '_is_admin',
    '_is_parent',
    '_is_teacher',
    '_teacher_classroom_ids',
    '_teacher_subject_ids',
    '_validate_student_for_user',
]
