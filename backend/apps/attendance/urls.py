from django.urls import path
from .views import (
    AttendanceListCreateView,
    AttendanceDetailView,
    BulkAttendanceView,
    StudentAttendanceView,
    AttendanceSummaryView,
    DailyAttendanceView,
)

app_name = 'attendance'

urlpatterns = [
    path('', AttendanceListCreateView.as_view(), name='attendance-list-create'),
    path('<int:pk>/', AttendanceDetailView.as_view(), name='attendance-detail'),
    path('bulk/', BulkAttendanceView.as_view(), name='attendance-bulk'),
    path('student/<int:student_id>/', StudentAttendanceView.as_view(), name='student-attendance'),
    path('daily/<str:date>/', DailyAttendanceView.as_view(), name='daily-attendance'),
    path('summary/', AttendanceSummaryView.as_view(), name='attendance-summary'),
]
