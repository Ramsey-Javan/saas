from django.urls import path
from .views import (
    StudentListCreateView,
    StudentDetailView,
    StudentByAdmissionView,
    AdmissionListCreateView,
    AdmissionDetailView,
    StudentAdmissionsView,
    GradeLevelStatsView,
)

app_name = 'students'

urlpatterns = [
    path('', StudentListCreateView.as_view(), name='student-list-create'),
    path('<int:pk>/', StudentDetailView.as_view(), name='student-detail'),
    path('by-admission/<str:admission_number>/', StudentByAdmissionView.as_view(), name='student-by-admission'),
    path('<int:student_id>/admissions/', StudentAdmissionsView.as_view(), name='student-admissions'),
    path('admissions/', AdmissionListCreateView.as_view(), name='admission-list-create'),
    path('admissions/<int:pk>/', AdmissionDetailView.as_view(), name='admission-detail'),
    path('stats/grade-levels/', GradeLevelStatsView.as_view(), name='grade-level-stats'),
]
