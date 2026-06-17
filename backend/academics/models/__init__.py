"""Academics models package — re-exports all models for backwards compatibility."""
from .base import TenantModel
from .curriculum import (
    ClassSubjectAssignment,
    LearningOutcome,
    Strand,
    Subject,
    SubStrand,
    TERM_CHOICES,
)
from .grades import (
    CBCGrade,
    ExamCBCSync,
    ExamConfig,
    ExamResult,
    ExamSetup,
    ExamSubject,
)
from .national_exams import (
    NationalExamCandidate,
    NationalExamResult,
    NationalExamSession,
)
from .school_life import (
    AttendanceRecord,
    AttendanceSession,
    ClassTimetable,
    CoCurricularActivity,
    ReportCard,
    StudentCoCurricular,
)

__all__ = [
    'AttendanceRecord',
    'AttendanceSession',
    'CBCGrade',
    'ClassSubjectAssignment',
    'ClassTimetable',
    'CoCurricularActivity',
    'ExamCBCSync',
    'ExamConfig',
    'ExamResult',
    'ExamSetup',
    'ExamSubject',
    'LearningOutcome',
    'NationalExamCandidate',
    'NationalExamResult',
    'NationalExamSession',
    'ReportCard',
    'Strand',
    'StudentCoCurricular',
    'Subject',
    'SubStrand',
    'TenantModel',
    'TERM_CHOICES',
]