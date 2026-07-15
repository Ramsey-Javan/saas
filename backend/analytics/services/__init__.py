"""Re-exports every analytics service function so views.py can do
`from analytics import services` and call `services.get_x(...)` without
caring which internal module a given function actually lives in.
"""
from .school import get_school_overview, get_term_summary, get_school_classrooms
from .exam import get_exam_breakdown, get_class_rankings, get_subject_analysis
from .classroom import get_class_performance, get_class_ranking, get_grade_distribution
from .subject import get_subject_comparison, get_subject_school_analysis, get_cohort_reference
from .student import (
    get_student_profile, get_student_report_card,
    get_student_performance, get_student_longitudinal,
)
from .tracker import get_improvement_tracker
from .warning import get_early_warning
from .teacher_scope import get_teacher_scope, get_teacher_overview  # <-- ADD get_teacher_overview
from .exceptions import AnalyticsError, InsufficientDataError, InvalidFilterError
from .subject_teacher import get_subject_teacher_overview, get_subject_teacher_early_warning

__all__ = [
    "get_school_overview",
    "get_term_summary",
    "get_school_classrooms",
    "get_exam_breakdown",
    "get_class_rankings",
    "get_subject_analysis",
    "get_class_performance",
    "get_class_ranking",
    "get_grade_distribution",
    "get_subject_comparison",
    "get_subject_school_analysis",
    "get_cohort_reference",
    "get_student_profile",
    "get_student_report_card",
    "get_student_performance",
    "get_student_longitudinal",
    "get_improvement_tracker",
    "get_early_warning",
    "get_teacher_scope",
    "get_teacher_overview",          
    "AnalyticsError",
    "InsufficientDataError",
    "InvalidFilterError",
    "get_subject_teacher_overview",
    "get_subject_teacher_early_warning",
]