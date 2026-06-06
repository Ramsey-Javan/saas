from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AttendanceSessionViewSet,
    CBCGradeViewSet,
    ClassSubjectAssignmentViewSet,
    ClassTimetableViewSet,
    CoCurricularActivityViewSet,
    ExamConfigViewSet,
    ExamResultViewSet,
    ExamSetupViewSet,
    LearningOutcomeViewSet,
    NationalExamCandidateViewSet,
    NationalExamResultViewSet,
    NationalExamSessionViewSet,
    ReportCardViewSet,
    StrandViewSet,
    StudentCoCurricularViewSet,
    SubjectViewSet,
    SubStrandViewSet,
)

router = DefaultRouter()
router.register('subjects', SubjectViewSet, basename='subject')
router.register('strands', StrandViewSet, basename='strand')
router.register('sub-strands', SubStrandViewSet, basename='substrand')
router.register('outcomes', LearningOutcomeViewSet, basename='outcome')
router.register('assignments', ClassSubjectAssignmentViewSet, basename='assignment')
router.register('grades', CBCGradeViewSet, basename='grade')
router.register('exam-config', ExamConfigViewSet, basename='examconfig')
router.register('exam-setups', ExamSetupViewSet, basename='examsetup')
router.register('exam-results', ExamResultViewSet, basename='examresult')
router.register('national-exam-sessions', NationalExamSessionViewSet, basename='nationalexamsession')
router.register('national-exam-candidates', NationalExamCandidateViewSet, basename='nationalexamcandidate')
router.register('national-exam-results', NationalExamResultViewSet, basename='nationalexamresult')
router.register('sessions', AttendanceSessionViewSet, basename='session')
router.register('timetables', ClassTimetableViewSet, basename='timetable')
router.register('activities', CoCurricularActivityViewSet, basename='activity')
router.register('co-curricular', StudentCoCurricularViewSet, basename='cocurricular')
router.register('report-cards', ReportCardViewSet, basename='reportcard')

urlpatterns = [
    path('exam-config/', ExamConfigViewSet.as_view({'get': 'list', 'put': 'update'}), name='examconfig-root'),
    path('', include(router.urls)),
]
