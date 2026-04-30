from django.urls import path
from .views import (
    SubjectListCreateView,
    SubjectDetailView,
    AssessmentListCreateView,
    AssessmentDetailView,
    BulkAssessmentCreateView,
    StudentAssessmentsView,
    ReportCardListCreateView,
    ReportCardDetailView,
    StudentReportCardsView,
)

app_name = 'grading'

urlpatterns = [
    path('subjects/', SubjectListCreateView.as_view(), name='subject-list-create'),
    path('subjects/<int:pk>/', SubjectDetailView.as_view(), name='subject-detail'),
    path('assessments/', AssessmentListCreateView.as_view(), name='assessment-list-create'),
    path('assessments/<int:pk>/', AssessmentDetailView.as_view(), name='assessment-detail'),
    path('assessments/bulk/', BulkAssessmentCreateView.as_view(), name='assessment-bulk-create'),
    path('assessments/student/<int:student_id>/', StudentAssessmentsView.as_view(), name='student-assessments'),
    path('report-cards/', ReportCardListCreateView.as_view(), name='report-card-list-create'),
    path('report-cards/<int:pk>/', ReportCardDetailView.as_view(), name='report-card-detail'),
    path('report-cards/student/<int:student_id>/', StudentReportCardsView.as_view(), name='student-report-cards'),
]
