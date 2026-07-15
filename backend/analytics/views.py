"""Thin views for the analytics API.
Every view here does exactly three things: validate query params, check
permissions (via permissions.py), and call the matching service function.
All actual computation and query logic lives in analytics/services/.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from academics.views.mixins import _is_teacher
from students.models import Classroom, Student
from academics.views.mixins import _is_admin, _is_teacher
from . import services
from .services.exceptions import AnalyticsError, InsufficientDataError
from .permissions import (
    IsAdminOnly, CanViewTermSummary, CanViewExamBreakdown, CanViewClassRankings,
    CanViewSubjectAnalysis, CanViewClassroomTermData, CanViewCohortReference,
    CanViewStudentProfile, CanViewImprovementTracker, CanViewEarlyWarning,
    CanViewSubjectTeacherSummary,
    _teacher_is_class_teacher, _teacher_assigned_subject_ids_for_exam,
)
from .serializers import (
    AcademicYearFilterSerializer, TermSummaryFilterSerializer, ExamFilterSerializer,
    SubjectAnalysisFilterSerializer, StudentProfileFilterSerializer,
    StudentReportCardFilterSerializer, ClassroomYearFilterSerializer,
    ClassroomTermFilterSerializer, GradeDistributionFilterSerializer,
    CohortReferenceFilterSerializer, SubjectSchoolAnalysisFilterSerializer,
    EarlyWarningFilterSerializer, SchoolClassroomsFilterSerializer,
)
def _handle(fn, *args, **kwargs):
    """Run a service function, translating AnalyticsError into a clean response."""
    try:
        data = fn(*args, **kwargs)
        return Response(data)
    except InsufficientDataError as exc:
        # Return 200 so the frontend treats "no data yet" as a normal empty
        # state rather than a hard 400 error.  UI checks response.empty to
        # decide whether to render charts or an EmptyState.
        return Response(
            {**exc.to_response_data(), "empty": True},
            status=status.HTTP_200_OK,
        )
    except AnalyticsError as exc:
        return Response(exc.to_response_data(), status=status.HTTP_400_BAD_REQUEST)
    
# --- Helper functions for secure, tenant-scoped object resolution ---
def _resolve_student(request, student_id):
    if not student_id:
        return None
    return Student.objects.filter(id=student_id, tenant=request.user.tenant).first()

def _resolve_exam(request, exam_id):
    if not exam_id:
        return None
    from academics.models import Exam
    return Exam.objects.filter(id=exam_id, tenant=request.user.tenant).first()

def _resolve_classroom(request, classroom_id):
    if not classroom_id:
        return None
    return Classroom.objects.filter(id=classroom_id, tenant=request.user.tenant).first()


# ── School / Term (Level 4 / Level 3, Lens A) ──────────────────────────

class SchoolOverviewView(APIView):
    """School overview: admin sees full school; class teacher sees only
    their own classroom(s); subject teacher sees a minimal dashboard."""
    permission_classes = [CanViewTermSummary]  # admin or teacher

    def get(self, request):
        params = AcademicYearFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        academic_year = params.validated_data['academic_year']

        # If teacher, return scoped overview for their classrooms only
        if _is_teacher(request.user) and not _is_admin(request.user):
            return _handle(
                services.get_teacher_overview,
                request.user.tenant,
                request.user,
                academic_year,
            )

        return _handle(services.get_school_overview, request.user.tenant, academic_year)
class TermSummaryView(APIView):
    permission_classes = [CanViewTermSummary]
    def get(self, request):
        params = TermSummaryFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return _handle(
            services.get_term_summary,
            request.user.tenant,
            params.validated_data['academic_year'],
            params.validated_data['term'],
        )

class SchoolClassroomsView(APIView):
    """All classrooms for a tenant/year/term with performance metrics,
    grouped by grade_level with stream breakdown."""
    permission_classes = [IsAdminOnly]
    def get(self, request):
        params = SchoolClassroomsFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return _handle(
            services.get_school_classrooms,
            request.user.tenant,
            params.validated_data['academic_year'],
            params.validated_data['term'],
        )

# ── Exam-scoped (Level 2, Lens B/C) ─────────────────────────────────────

class ExamBreakdownView(APIView):
    permission_classes = [CanViewExamBreakdown]
    def get(self, request):
        params = ExamFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        exam_id = params.validated_data.get('exam_id') or request.query_params.get('exam_id')
        exam = _resolve_exam(request, exam_id)
        if not exam:
            return Response({'error': 'Exam not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        response = _handle(services.get_exam_breakdown, request.user.tenant, exam.id)
        if (
            response.status_code == 200
            and _is_teacher(request.user)
            and not _teacher_is_class_teacher(request.user, exam.classroom)
        ):
            allowed = _teacher_assigned_subject_ids_for_exam(request.user, exam)
            response.data['subjects'] = [
                s for s in response.data['subjects'] if s['subject']['id'] in allowed
            ]
        return response

class ClassRankingsView(APIView):
    """Exam-scoped rankings (one specific exam). See ClassRankingView
    below for the term-wide (all exams combined) version."""
    permission_classes = [CanViewClassRankings]
    def get(self, request):
        params = ExamFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        exam_id = params.validated_data.get('exam_id') or request.query_params.get('exam_id')
        exam = _resolve_exam(request, exam_id)
        if not exam:
            return Response({'error': 'Exam not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(services.get_class_rankings, request.user.tenant, exam.id)

class SubjectAnalysisView(APIView):
    permission_classes = [CanViewSubjectAnalysis]
    def get(self, request):
        params = SubjectAnalysisFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        exam_id = params.validated_data.get('exam_id') or request.query_params.get('exam_id')
        exam = _resolve_exam(request, exam_id)
        if not exam:
            return Response({'error': 'Exam not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        subject_id = params.validated_data.get('subject_id')
        is_class_teacher = not _is_teacher(request.user) or _teacher_is_class_teacher(request.user, exam.classroom)

        if _is_teacher(request.user) and not is_class_teacher:
            allowed = _teacher_assigned_subject_ids_for_exam(request.user, exam)
            if subject_id is not None and subject_id not in allowed:
                return Response(
                    {'error': 'You are not assigned to this subject for this exam.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        response = _handle(services.get_subject_analysis, request.user.tenant, exam.id, subject_id)
        if response.status_code == 200 and _is_teacher(request.user) and not is_class_teacher:
            allowed = _teacher_assigned_subject_ids_for_exam(request.user, exam)
            response.data['subjects'] = [
                s for s in response.data['subjects'] if s['subject']['id'] in allowed
            ]
        return response

# ── Classroom + Term (the "Term x Class" view) ──────────────────────────

class ClassPerformanceView(APIView):
    permission_classes = [CanViewClassroomTermData]
    def get(self, request):
        params = ClassroomTermFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        classroom_id = params.validated_data.get('classroom_id') or request.query_params.get('classroom_id')
        classroom = _resolve_classroom(request, classroom_id)
        if not classroom:
            return Response({'error': 'Classroom not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(
            services.get_class_performance, request.user.tenant, classroom,
            params.validated_data['term'], params.validated_data['academic_year'],
        )

class ClassRankingView(APIView):
    """Term-wide rankings for one classroom (all exams that term
    combined). See ClassRankingsView above for the single-exam version."""
    permission_classes = [CanViewClassroomTermData]
    def get(self, request):
        params = ClassroomTermFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        classroom_id = params.validated_data.get('classroom_id') or request.query_params.get('classroom_id')
        classroom = _resolve_classroom(request, classroom_id)
        if not classroom:
            return Response({'error': 'Classroom not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(
            services.get_class_ranking, request.user.tenant, classroom,
            params.validated_data['term'], params.validated_data['academic_year'],
        )

class GradeDistributionView(APIView):
    permission_classes = [CanViewClassroomTermData]
    def get(self, request):
        params = GradeDistributionFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        classroom_id = params.validated_data.get('classroom_id') or request.query_params.get('classroom_id')
        classroom = _resolve_classroom(request, classroom_id)
        if not classroom:
            return Response({'error': 'Classroom not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(
            services.get_grade_distribution, request.user.tenant, classroom,
            params.validated_data['exam_type'], params.validated_data['term'],
            params.validated_data['academic_year'],
        )

class SubjectComparisonView(APIView):
    permission_classes = [CanViewClassroomTermData]
    def get(self, request):
        params = ClassroomTermFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        classroom_id = params.validated_data.get('classroom_id') or request.query_params.get('classroom_id')
        classroom = _resolve_classroom(request, classroom_id)
        if not classroom:
            return Response({'error': 'Classroom not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(
            services.get_subject_comparison, request.user.tenant, classroom,
            params.validated_data['term'], params.validated_data['academic_year'],
        )

class CohortReferenceView(APIView):
    permission_classes = [CanViewCohortReference]
    def get(self, request):
        params = CohortReferenceFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        classroom_id = params.validated_data.get('classroom_id') or request.query_params.get('classroom_id')
        classroom = _resolve_classroom(request, classroom_id)
        if not classroom:
            return Response({'error': 'Classroom not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        from academics.models import Subject
        subject = Subject.objects.filter(id=params.validated_data['subject_id'], tenant=request.user.tenant).first()
        if not subject:
            return Response({'error': 'Subject not found.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(
            services.get_cohort_reference, request.user.tenant, classroom, subject,
            params.validated_data['term'], params.validated_data['academic_year'],
        )

# ── Cross-class subject analysis (admin only) ───────────────────────────

class SubjectSchoolAnalysisView(APIView):
    permission_classes = [IsAdminOnly]
    def get(self, request):
        params = SubjectSchoolAnalysisFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        from academics.models import Subject
        subject = Subject.objects.filter(id=params.validated_data['subject_id'], tenant=request.user.tenant).first()
        if not subject:
            return Response({'error': 'Subject not found.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(
            services.get_subject_school_analysis, request.user.tenant, subject,
            params.validated_data['term'], params.validated_data['academic_year'],
        )

# ── Student (Lens B) ─────────────────────────────────────────────────────

class StudentProfileView(APIView):
    """Original exam-scoped year view. Not called by the current
    frontend -- kept for a possible future use."""
    permission_classes = [CanViewStudentProfile]
    def get(self, request):
        params = StudentProfileFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        student_id = params.validated_data.get('student_id') or request.query_params.get('student_id')
        student = _resolve_student(request, student_id)
        if not student:
            return Response({'error': 'Student not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(
            services.get_student_profile,
            request.user.tenant, student, params.validated_data['academic_year'],
        )

class StudentReportCardView(APIView):
    """Original exam-grouped-under-subject term view. Not called by the
    current frontend -- kept for a possible future use."""
    permission_classes = [CanViewStudentProfile]
    def get(self, request):
        params = StudentReportCardFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        student_id = params.validated_data.get('student_id') or request.query_params.get('student_id')
        student = _resolve_student(request, student_id)
        if not student:
            return Response({'error': 'Student not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(
            services.get_student_report_card,
            request.user.tenant, student,
            params.validated_data['term'], params.validated_data['academic_year'],
        )

class StudentPerformanceView(APIView):
    """What the frontend actually calls: one term, flattened rows,
    class_average + rank_in_subject per row."""
    permission_classes = [CanViewStudentProfile]
    def get(self, request):
        params = StudentReportCardFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        student_id = params.validated_data.get('student_id') or request.query_params.get('student_id')
        student = _resolve_student(request, student_id)
        if not student:
            return Response({'error': 'Student not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(
            services.get_student_performance,
            request.user.tenant, student,
            params.validated_data['term'], params.validated_data['academic_year'],
        )

class StudentLongitudinalView(APIView):
    """What the frontend actually calls: full year, bucketed by term,
    with trend/velocity."""
    permission_classes = [CanViewStudentProfile]
    def get(self, request):
        params = StudentProfileFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        student_id = params.validated_data.get('student_id') or request.query_params.get('student_id')
        student = _resolve_student(request, student_id)
        if not student:
            return Response({'error': 'Student not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(
            services.get_student_longitudinal,
            request.user.tenant, student, params.validated_data['academic_year'],
        )

# ── Improvement Tracker ──────────────────────────────────────────────────

class ImprovementTrackerView(APIView):
    permission_classes = [CanViewImprovementTracker]
    def get(self, request):
        params = ClassroomYearFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        classroom_id = params.validated_data.get('classroom_id') or request.query_params.get('classroom_id')
        classroom = _resolve_classroom(request, classroom_id)
        if not classroom:
            return Response({'error': 'Classroom not found in this school.'}, status=status.HTTP_404_NOT_FOUND)

        return _handle(
            services.get_improvement_tracker,
            request.user.tenant, classroom, params.validated_data['academic_year'],
        )

# ── Early Warning ────────────────────────────────────────────────────────

class EarlyWarningView(APIView):
    permission_classes = [CanViewEarlyWarning]

    def get(self, request):
        params = EarlyWarningFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        term = params.validated_data['term']
        academic_year = params.validated_data['academic_year']

        # Check if user is a subject teacher (not class teacher, not admin)
        is_subject_teacher_only = (
            _is_teacher(request.user)
            and not _is_admin(request.user)
            and not Classroom.objects.filter(tenant=request.user.tenant, class_teacher=request.user).exists()
        )

        if is_subject_teacher_only:
            from .services.subject_teacher import get_subject_teacher_early_warning
            return _handle(
                get_subject_teacher_early_warning,
                request.user.tenant,
                request.user,
                term,
                academic_year,
            )

        response = _handle(services.get_early_warning, request.user.tenant, term, academic_year)

        # ── FIX: if the backend returned an empty-state envelope, pass it
        # through untouched — there are no students to filter.
        if response.status_code == 200 and response.data.get('empty'):
            return response

        # Class teachers only ever see their own classroom's slice
        if response.status_code == 200 and _is_teacher(request.user) and not _is_admin(request.user):
            classroom_id = params.validated_data.get('classroom_id')
            teacher_classrooms = {
                c.id for c in Classroom.objects.filter(tenant=request.user.tenant, class_teacher=request.user)
            }
            if classroom_id is not None and classroom_id not in teacher_classrooms:
                return Response(
                    {'error': 'You are not the class teacher for that classroom.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            allowed_ids = {classroom_id} if classroom_id is not None else teacher_classrooms
            response.data['students'] = [
                e for e in response.data['students']
                if e['student'].get('classroom') and e['student']['classroom']['id'] in allowed_ids
            ]
            response.data['at_risk_count'] = len(response.data['students'])

        return response
    
# ── Teacher Scope ──────────────────────────────────────────────────────

class TeacherScopeView(APIView):
    """Returns what the current user can see in analytics.
    Used by the frontend to conditionally render dashboard sections."""
    permission_classes = [CanViewTermSummary]  # any teacher or admin

    def get(self, request):
        data = services.get_teacher_scope(request.user.tenant, request.user)
        return Response(data)
    
class SubjectTeacherSummaryView(APIView):
    """Subject teacher overview: returns analytics scoped to the subjects
    this teacher teaches, organized by classroom."""
    permission_classes = [CanViewSubjectTeacherSummary]

    def get(self, request):
        params = AcademicYearFilterSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        academic_year = params.validated_data['academic_year']
        term = request.query_params.get('term')  # Optional

        # Subject teacher: return subject-scoped overview
        if _is_teacher(request.user) and not _is_admin(request.user):
            from .services.subject_teacher import get_subject_teacher_overview
            return _handle(
                get_subject_teacher_overview,
                request.user.tenant,
                request.user,
                academic_year,
                term,
            )

        # Admin or class teacher: return empty structure (they use other endpoints)
        return Response({
            "academic_year": academic_year,
            "term": term,
            "is_subject_teacher_view": True,
            "subjects": [],
            "subject_classrooms": [],
            "term_trend": [],
            "grade_distribution": {"counts": {"EE": 0, "ME": 0, "AE": 0, "BE": 0}, "percentages": {"EE": "0.00", "ME": "0.00", "AE": "0.00", "BE": "0.00"}},
            "top_students": [],
            "bottom_students": [],
            "early_warning_count": 0,
        })

# ── Subject Teacher Drill-down ───────────────────────────────────────────

class SubjectTeacherClassroomsView(APIView):
    """Subject-scoped classroom breakdown for a subject teacher.
    Returns per-classroom performance for ONE subject they teach."""
    permission_classes = [CanViewSubjectTeacherSummary]

    def get(self, request):
        from .services.subject_teacher import get_subject_teacher_classrooms

        subject_id = request.query_params.get('subject_id')
        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')

        if not subject_id:
            return Response({'error': 'subject_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not academic_year:
            return Response({'error': 'academic_year is required.'}, status=status.HTTP_400_BAD_REQUEST)

        return _handle(
            get_subject_teacher_classrooms,
            request.user.tenant,
            request.user,
            subject_id,
            int(academic_year),
            term,
        )