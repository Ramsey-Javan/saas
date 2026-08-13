from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    PeriodViewSet,
    ReadinessView,
    RoomResourceViewSet,
    ScheduleTemplateViewSet,
    SubjectRuleViewSet,
    TeacherAvailabilityViewSet,
    TeacherSubjectAssignmentViewSet,
    TeacherWorkloadLimitViewSet,
    TimetableEntryViewSet,
    TimetableJobViewSet,
    TimetablePDFDownloadView
)

router = DefaultRouter()
router.register('schedule-templates', ScheduleTemplateViewSet, basename='schedule-template')
router.register('periods', PeriodViewSet, basename='period')
router.register('rooms', RoomResourceViewSet, basename='room-resource')
router.register('subject-rules', SubjectRuleViewSet, basename='subject-rule')
router.register('teacher-availability', TeacherAvailabilityViewSet, basename='teacher-availability')
router.register('teacher-workload-limits', TeacherWorkloadLimitViewSet, basename='teacher-workload-limit')
router.register('teacher-subject-assignments', TeacherSubjectAssignmentViewSet, basename='teacher-subject-assignment')
router.register('jobs', TimetableJobViewSet, basename='timetable-job')
router.register('entries', TimetableEntryViewSet, basename='timetable-entry')
# REMOVED: router.register('pdf-download', ...)

urlpatterns = [
    path('readiness/', ReadinessView.as_view(), name='timetable-readiness'),
    path('pdf/', TimetablePDFDownloadView.as_view(), name='timetable-pdf'),
    path('', include(router.urls)),
]

