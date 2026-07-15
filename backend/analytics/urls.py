"""Routes for the analytics API.

Read-only GET aggregations -- no ViewSets/routers needed.
"""
from django.urls import path

from .views import (
    SchoolOverviewView, TeacherScopeView, TermSummaryView, SchoolClassroomsView,
    ExamBreakdownView, ClassRankingsView, SubjectAnalysisView,
    ClassPerformanceView, ClassRankingView, GradeDistributionView,
    SubjectComparisonView, CohortReferenceView, SubjectSchoolAnalysisView,
    StudentProfileView, StudentReportCardView,
    StudentPerformanceView, StudentLongitudinalView,
    ImprovementTrackerView, EarlyWarningView, SubjectTeacherSummaryView,
    SubjectTeacherClassroomsView,
)

urlpatterns = [
    # School / Term (Level 4 / 3, Lens A)
    path('school-summary/', SchoolOverviewView.as_view(), name='analytics-school-summary'),
    path('term-summary/', TermSummaryView.as_view(), name='analytics-term-summary'),
    path('school-classrooms/', SchoolClassroomsView.as_view(), name='analytics-school-classrooms'),

    # Exam-scoped (Level 2, single exam event)
    path('exam-breakdown/', ExamBreakdownView.as_view(), name='analytics-exam-breakdown'),
    path('class-rankings/', ClassRankingsView.as_view(), name='analytics-class-rankings'),
    path('subject-analysis/', SubjectAnalysisView.as_view(), name='analytics-subject-analysis'),

    # Classroom + Term (whole term, all exams combined for one class)
    path('class-performance/', ClassPerformanceView.as_view(), name='analytics-class-performance'),
    path('class-ranking/', ClassRankingView.as_view(), name='analytics-class-ranking'),
    path('grade-distribution/', GradeDistributionView.as_view(), name='analytics-grade-distribution'),
    path('subject-comparison/', SubjectComparisonView.as_view(), name='analytics-subject-comparison'),
    path('cohort-reference/', CohortReferenceView.as_view(), name='analytics-cohort-reference'),

    # Cross-class, one subject school-wide (admin only)
    path('subject-school-analysis/', SubjectSchoolAnalysisView.as_view(), name='analytics-subject-school-analysis'),

    # Student
    path('student-profile/', StudentProfileView.as_view(), name='analytics-student-profile'),
    path('student-report-card/', StudentReportCardView.as_view(), name='analytics-student-report-card'),
    path('student-performance/', StudentPerformanceView.as_view(), name='analytics-student-performance'),
    path('student-longitudinal/', StudentLongitudinalView.as_view(), name='analytics-student-longitudinal'),

    # Improvement Tracker + Early Warning
    path('improvement-tracker/', ImprovementTrackerView.as_view(), name='analytics-improvement-tracker'),
    path('early-warning/', EarlyWarningView.as_view(), name='analytics-early-warning'),

    # Teacher
    path('teacher-scope/', TeacherScopeView.as_view(), name='analytics-teacher-scope'),
    path('subject-teacher-summary/', SubjectTeacherSummaryView.as_view(), name='analytics-subject-teacher-summary'),
    path('subject-teacher-classrooms/', SubjectTeacherClassroomsView.as_view(), name='analytics-subject-teacher-classrooms'),
]