import csv
import io
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from students.models import Classroom, Student

from .models import (
    AttendanceRecord,
    AttendanceSession,
    CBCGrade,
    ClassSubjectAssignment,
    ClassTimetable,
    CoCurricularActivity,
    ExamCBCSync,
    ExamConfig,
    ExamResult,
    ExamSetup,
    ExamSubject,
    LearningOutcome,
    NationalExamCandidate,
    NationalExamResult,
    NationalExamSession,
    ReportCard,
    Strand,
    StudentCoCurricular,
    Subject,
    SubStrand,
)
from .permissions import (
    CanViewReportCard,
    CanViewTimetable,
    CanViewExamResult,
    IsAdminUser,
    IsTeacherOrAdmin,
    user_owns_student,
)
from .serializers import (
    AttendanceSessionListSerializer,
    AttendanceSessionSerializer,
    BulkGradeSerializer,
    CBCGradeSerializer,
    ClassSubjectAssignmentSerializer,
    ClassTimetableSerializer,
    CoCurricularActivitySerializer,
    BulkExamResultSerializer,
    ExamCBCSyncSerializer,
    ExamConfigSerializer,
    ExamResultSerializer,
    ExamSetupListSerializer,
    ExamSetupSerializer,
    ExamSubjectSerializer,
    GenerateReportCardSerializer,
    LearningOutcomeSerializer,
    MarkAttendanceSerializer,
    NationalExamCandidateSerializer,
    NationalExamResultSerializer,
    NationalExamSessionSerializer,
    ReportCardSerializer,
    StrandSerializer,
    StudentCoCurricularSerializer,
    SubjectListSerializer,
    SubjectSerializer,
    SubStrandSerializer,
)
from .utils import load_knec_curriculum


class TenantScopedMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = getattr(self.request.user, 'tenant', None)
        if tenant:
            return queryset.filter(tenant=tenant)
        if getattr(self.request.user, 'is_superuser', False):
            return queryset
        return queryset.none()

    def perform_create(self, serializer):
        tenant = getattr(self.request.user, 'tenant', None)
        if not tenant and not getattr(self.request.user, 'is_superuser', False):
            raise PermissionDenied('Academics records must be created under a school tenant.')
        serializer.save(tenant=tenant)


def _teacher_classroom_ids(user):
    return ClassSubjectAssignment.objects.filter(tenant=user.tenant, teacher=user).values_list('classroom_id', flat=True)


def _teacher_subject_ids(user):
    return ClassSubjectAssignment.objects.filter(tenant=user.tenant, teacher=user).values_list('subject_id', flat=True)


def _is_admin(user):
    return getattr(user, 'role', None) in ('admin', 'superadmin')


def _is_teacher(user):
    return getattr(user, 'role', None) == 'teacher'


def _is_parent(user):
    return getattr(user, 'role', None) in ('parent', 'guardian')


def _validate_student_for_user(user, student_id):
    student = Student.objects.filter(id=student_id, tenant=user.tenant).select_related('primary_guardian').first()
    if not student:
        raise ValidationError({'student': 'Student not found in this school.'})
    if _is_teacher(user) and student.classroom_id not in set(_teacher_classroom_ids(user)):
        raise PermissionDenied('You can only access students in your assigned classes.')
    if _is_parent(user) and not user_owns_student(user, student):
        raise PermissionDenied('You can only access your own child.')
    return student


class SubjectViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.prefetch_related('strands__sub_strands__outcomes').all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active', 'is_preloaded']
    search_fields = ['name', 'code']
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(id__in=_teacher_subject_ids(self.request.user))
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return SubjectListSerializer
        return SubjectSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'load_curriculum']:
            return [IsAdminUser()]
        return [IsTeacherOrAdmin()]

    def perform_destroy(self, instance):
        if instance.is_preloaded:
            raise ValidationError('Cannot delete KNEC pre-loaded subjects. Deactivate instead.')
        instance.delete()

    @action(detail=False, methods=['post'], url_path='load-curriculum')
    def load_curriculum(self, request):
        tenant = request.user.tenant
        counts = load_knec_curriculum(tenant)
        total = sum(counts.values())
        message = 'CBC curriculum already loaded.'
        status_code = status.HTTP_200_OK
        if total:
            message = (
                f'CBC curriculum updated. {total} records added '
                f'({counts["subjects"]} subjects, {counts["strands"]} strands, '
                f'{counts["sub_strands"]} sub-strands, {counts["learning_outcomes"]} outcomes).'
            )
            status_code = status.HTTP_201_CREATED
        return Response({'message': message, **counts}, status=status_code)


class StrandViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Strand.objects.select_related('subject').all()
    serializer_class = StrandSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['subject']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(subject_id__in=_teacher_subject_ids(self.request.user))
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsTeacherOrAdmin()]

    def perform_create(self, serializer):
        subject = serializer.validated_data['subject']
        if subject.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Subject must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)

    def perform_update(self, serializer):
        subject = serializer.validated_data.get('subject', serializer.instance.subject)
        if subject.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Subject must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)


class SubStrandViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = SubStrand.objects.select_related('strand__subject').all()
    serializer_class = SubStrandSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['strand', 'strand__subject']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(strand__subject_id__in=_teacher_subject_ids(self.request.user))
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsTeacherOrAdmin()]

    def perform_create(self, serializer):
        strand = serializer.validated_data['strand']
        if strand.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Strand must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)

    def perform_update(self, serializer):
        strand = serializer.validated_data.get('strand', serializer.instance.strand)
        if strand.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Strand must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)


class LearningOutcomeViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = LearningOutcome.objects.select_related('sub_strand__strand__subject').all()
    serializer_class = LearningOutcomeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sub_strand', 'sub_strand__strand', 'sub_strand__strand__subject']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(sub_strand__strand__subject_id__in=_teacher_subject_ids(self.request.user))
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsTeacherOrAdmin()]

    def perform_create(self, serializer):
        sub_strand = serializer.validated_data['sub_strand']
        if sub_strand.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Sub-strand must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)

    def perform_update(self, serializer):
        sub_strand = serializer.validated_data.get('sub_strand', serializer.instance.sub_strand)
        if sub_strand.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Sub-strand must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)


class ClassSubjectAssignmentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = ClassSubjectAssignment.objects.select_related('classroom', 'subject', 'teacher').order_by(
        '-academic_year', 'term', 'classroom__name', 'subject__name'
    )
    serializer_class = ClassSubjectAssignmentSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['classroom', 'subject', 'teacher', 'academic_year', 'term']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(teacher=self.request.user)
        return qs

    def get_permissions(self):
        if self.action == 'my_classes':
            return [IsTeacherOrAdmin()]
        return [IsAdminUser()]

    def perform_create(self, serializer):
        classroom = serializer.validated_data['classroom']
        subject = serializer.validated_data['subject']
        teacher = serializer.validated_data.get('teacher')
        if classroom.tenant_id != self.request.user.tenant_id or subject.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom and subject must belong to your school.')
        if teacher and teacher.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Teacher must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)

    def perform_update(self, serializer):
        classroom = serializer.validated_data.get('classroom', serializer.instance.classroom)
        subject = serializer.validated_data.get('subject', serializer.instance.subject)
        teacher = serializer.validated_data.get('teacher', serializer.instance.teacher)
        if classroom.tenant_id != self.request.user.tenant_id or subject.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom and subject must belong to your school.')
        if teacher and teacher.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Teacher must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=False, methods=['get'], url_path='my-classes')
    def my_classes(self, request):
        qs = self.get_queryset()
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class CBCGradeViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = CBCGrade.objects.select_related(
        'student',
        'learning_outcome__sub_strand__strand__subject',
        'assessed_by',
    ).order_by('-academic_year', 'term', 'student__last_name', 'student__first_name')
    serializer_class = CBCGradeSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['student', 'term', 'academic_year', 'level', 'learning_outcome__sub_strand__strand__subject']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(
                student__classroom_id__in=_teacher_classroom_ids(self.request.user),
                learning_outcome__sub_strand__strand__subject_id__in=_teacher_subject_ids(self.request.user),
            )
        return qs

    def perform_create(self, serializer):
        student = serializer.validated_data['student']
        outcome = serializer.validated_data['learning_outcome']
        if student.tenant_id != self.request.user.tenant_id or outcome.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Student and learning outcome must belong to your school.')
        if _is_teacher(self.request.user):
            if student.classroom_id not in set(_teacher_classroom_ids(self.request.user)):
                raise PermissionDenied('You can only grade students in your assigned classes.')
            if outcome.sub_strand.strand.subject_id not in set(_teacher_subject_ids(self.request.user)):
                raise PermissionDenied('You can only grade your assigned subjects.')
        serializer.save(tenant=self.request.user.tenant, assessed_by=self.request.user)

    def perform_update(self, serializer):
        student = serializer.validated_data.get('student', serializer.instance.student)
        outcome = serializer.validated_data.get('learning_outcome', serializer.instance.learning_outcome)
        if student.tenant_id != self.request.user.tenant_id or outcome.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Student and learning outcome must belong to your school.')
        if _is_teacher(self.request.user):
            if student.classroom_id not in set(_teacher_classroom_ids(self.request.user)):
                raise PermissionDenied('You can only grade students in your assigned classes.')
            if outcome.sub_strand.strand.subject_id not in set(_teacher_subject_ids(self.request.user)):
                raise PermissionDenied('You can only grade your assigned subjects.')
        serializer.save(tenant=self.request.user.tenant, assessed_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk_grade(self, request):
        serializer = BulkGradeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant = request.user.tenant
        learning_outcome = data['learning_outcome']
        created = 0
        updated = 0
        errors = []

        if learning_outcome.tenant_id != tenant.id:
            raise ValidationError({'learning_outcome': 'Learning outcome not found in this school.'})
        if _is_teacher(request.user) and learning_outcome.sub_strand.strand.subject_id not in set(_teacher_subject_ids(request.user)):
            raise PermissionDenied('You can only grade your assigned subjects.')

        with transaction.atomic():
            for entry in data['grades']:
                student_id = entry.get('student_id')
                
                level = entry.get('level')
                remarks = entry.get('remarks', '')

                if not student_id or not level:
                    errors.append(f'Missing student_id or level: {entry}')
                    continue
                if level not in CBCGrade.Level.values:
                    errors.append(f'Invalid level for student {student_id}: {level}')
                    continue

                student = Student.objects.filter(id=student_id, tenant=tenant).first()
                if not student:
                    errors.append(f'Student {student_id} not found')
                    continue
                if _is_teacher(request.user) and student.classroom_id not in set(_teacher_classroom_ids(request.user)):
                    errors.append(f'Student {student_id} is not in your assigned classes')
                    continue

                _, created_flag = CBCGrade.objects.update_or_create(
                    tenant=tenant,
                    student=student,
                    learning_outcome=learning_outcome,
                    term=data['term'],
                    academic_year=data['academic_year'],
                    defaults={'level': level, 'remarks': remarks, 'assessed_by': request.user},
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1

        return Response({'created': created, 'updated': updated, 'errors': errors}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='import-csv', parser_classes=[MultiPartParser])
    def import_csv(self, request):
        file = request.FILES.get('file')
        term = request.data.get('term')
        academic_year = request.data.get('academic_year')

        if not file or not term or not academic_year:
            return Response({'error': 'file, term, academic_year required'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = request.user.tenant
        created = 0
        updated = 0
        errors = []
        reader = csv.DictReader(io.StringIO(file.read().decode('utf-8')))

        with transaction.atomic():
            for i, row in enumerate(reader, start=2):
                adm = row.get('admission_number', '').strip()
                outcome_id = row.get('outcome_id', '').strip()
                level = row.get('level', '').strip().upper()
                remarks = row.get('remarks', '').strip()

                if not adm or not outcome_id or not level:
                    errors.append(f'Row {i}: missing required fields')
                    continue
                if level not in CBCGrade.Level.values:
                    errors.append(f'Row {i}: invalid level {level}')
                    continue

                student = Student.objects.filter(tenant=tenant, admission_number=adm).first()
                if not student:
                    errors.append(f'Row {i}: student {adm} not found')
                    continue

                outcome = LearningOutcome.objects.filter(id=outcome_id, tenant=tenant).select_related('sub_strand__strand').first()
                if not outcome:
                    errors.append(f'Row {i}: outcome {outcome_id} not found')
                    continue
                if _is_teacher(request.user):
                    if student.classroom_id not in set(_teacher_classroom_ids(request.user)):
                        errors.append(f'Row {i}: student {adm} is not in your assigned classes')
                        continue
                    if outcome.sub_strand.strand.subject_id not in set(_teacher_subject_ids(request.user)):
                        errors.append(f'Row {i}: outcome {outcome_id} is not in your assigned subjects')
                        continue

                _, created_flag = CBCGrade.objects.update_or_create(
                    tenant=tenant,
                    student=student,
                    learning_outcome=outcome,
                    term=term,
                    academic_year=int(academic_year),
                    defaults={'level': level, 'remarks': remarks, 'assessed_by': request.user},
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1

        return Response({
            'created': created,
            'updated': updated,
            'errors': errors,
            'total_rows_processed': created + updated + len(errors),
        })

    @action(detail=False, methods=['get'], url_path='student-report')
    def student_report(self, request):
        student_id = request.query_params.get('student')
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')

        if not student_id:
            return Response({'error': 'student param required'}, status=status.HTTP_400_BAD_REQUEST)

        _validate_student_for_user(request.user, student_id)
        qs = self.get_queryset().filter(student_id=student_id)
        if term:
            qs = qs.filter(term=term)
        if academic_year:
            qs = qs.filter(academic_year=int(academic_year))

        result = {}
        for grade in qs:
            outcome = grade.learning_outcome
            sub_strand = outcome.sub_strand
            strand = sub_strand.strand
            subject = strand.subject

            subject_data = result.setdefault(subject.name, {
                'subject_id': subject.id,
                'subject_code': subject.code,
                'strands': {},
            })
            strand_data = subject_data['strands'].setdefault(strand.name, {
                'strand_id': strand.id,
                'sub_strands': {},
            })
            sub_strand_data = strand_data['sub_strands'].setdefault(sub_strand.name, {
                'sub_strand_id': sub_strand.id,
                'outcomes': [],
            })
            sub_strand_data['outcomes'].append({
                'outcome_id': outcome.id,
                'description': outcome.description,
                'level': grade.level,
                'remarks': grade.remarks,
            })

        return Response(result)

    @action(detail=False, methods=['get'], url_path='grade-sheet')
    def grade_sheet(self, request):
        classroom_id = request.query_params.get('classroom')
        subject_id = request.query_params.get('subject')
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')

        if not all([classroom_id, subject_id, term, academic_year]):
            return Response({'error': 'classroom, subject, term, academic_year required'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = request.user.tenant
        if _is_teacher(request.user):
            if int(classroom_id) not in set(_teacher_classroom_ids(request.user)):
                raise PermissionDenied('You can only access your assigned classes.')
            if int(subject_id) not in set(_teacher_subject_ids(request.user)):
                raise PermissionDenied('You can only access your assigned subjects.')

        students = Student.objects.filter(tenant=tenant, classroom_id=classroom_id, is_active=True).order_by('last_name', 'first_name')
        outcomes = LearningOutcome.objects.filter(
            sub_strand__strand__subject_id=subject_id,
            sub_strand__strand__subject__tenant=tenant,
        ).select_related('sub_strand__strand').order_by('sub_strand__strand__order', 'sub_strand__order', 'order')
        existing_grades = CBCGrade.objects.filter(
            tenant=tenant,
            student__classroom_id=classroom_id,
            learning_outcome__sub_strand__strand__subject_id=subject_id,
            term=term,
            academic_year=int(academic_year),
        )
        grade_map = {
            (g.student_id, g.learning_outcome_id): {'grade_id': g.id, 'level': g.level, 'remarks': g.remarks}
            for g in existing_grades
        }
        student_list = list(students)
        outcome_list = list(outcomes)

        return Response({
            'students': [
                {'id': s.id, 'name': s.get_full_name(), 'admission_number': s.admission_number}
                for s in student_list
            ],
            'outcomes': [
                {
                    'id': o.id,
                    'description': o.description,
                    'sub_strand': o.sub_strand.name,
                    'strand': o.sub_strand.strand.name,
                }
                for o in outcome_list
            ],
            'grades': {
                f'{student.id}_{outcome.id}': grade_map.get((student.id, outcome.id))
                for student in student_list
                for outcome in outcome_list
            },
        })


class ExamConfigViewSet(TenantScopedMixin, viewsets.ViewSet):
    permission_classes = [IsTeacherOrAdmin]

    def list(self, request):
        config = ExamConfig.get_for_tenant(request.user.tenant)
        return Response(ExamConfigSerializer(config).data)

    def update(self, request, pk=None):
        if not _is_admin(request.user):
            raise PermissionDenied('Only admins can update thresholds.')
        config = ExamConfig.get_for_tenant(request.user.tenant)
        serializer = ExamConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class ExamSetupViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = ExamSetup.objects.select_related('classroom', 'created_by').prefetch_related(
        'exam_subjects__subject',
        'exam_subjects__teacher',
        'cbc_syncs',
    ).all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['classroom', 'term', 'academic_year', 'exam_type', 'is_active']
    search_fields = ['name']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(classroom_id__in=_teacher_classroom_ids(self.request.user))
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return ExamSetupListSerializer
        return ExamSetupSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsTeacherOrAdmin()]

    def perform_create(self, serializer):
        classroom = serializer.validated_data['classroom']
        if classroom.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom must belong to your school.')
        serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)

    def perform_update(self, serializer):
        classroom = serializer.validated_data.get('classroom', serializer.instance.classroom)
        if classroom.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=True, methods=['post'], permission_classes=[IsTeacherOrAdmin], url_path='subjects')
    def add_subject(self, request, pk=None):
        exam = self.get_object()
        serializer = ExamSubjectSerializer(data={**request.data, 'exam': exam.id})
        serializer.is_valid(raise_exception=True)
        subject = serializer.validated_data['subject']
        teacher = serializer.validated_data.get('teacher')
        if subject.tenant_id != request.user.tenant_id:
            raise ValidationError('Subject must belong to your school.')
        if teacher and teacher.tenant_id != request.user.tenant_id:
            raise ValidationError('Teacher must belong to your school.')
        if _is_teacher(request.user) and teacher != request.user:
            raise PermissionDenied('Teachers can only assign themselves to exam subjects.')
        exam_subject = serializer.save(tenant=request.user.tenant, exam=exam)
        return Response(ExamSubjectSerializer(exam_subject).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsTeacherOrAdmin], url_path='sync-to-cbc')
    def sync_to_cbc(self, request, pk=None):
        """
        Sync exam results to CBC grades using realistic strand-level randomization.

        For each student's exam result (per subject):
          1. Get exam CBC level (e.g. ME)
          2. Get all strands for that subject (ordered)
          3. Call assign_strand_levels() to get realistic strand-level distribution
             that averages to exam level
          4. For each strand, get its learning outcomes
          5. Call assign_outcome_levels() to distribute outcome levels within +/-1 of strand level
          6. For each outcome:
             - If CBCGrade already exists, skip (preserve manual entry)
             - If CBCGrade does not exist, create with the computed level
        """
        from .utils import assign_strand_levels, assign_outcome_levels

        exam = self.get_object()
        tenant = request.user.tenant

        results = ExamResult.objects.filter(
            tenant=tenant,
            exam_subject__exam=exam,
        ).select_related(
            'student',
            'exam_subject__subject',
        )

        total_synced = 0
        total_skipped = 0

        with transaction.atomic():
            for result in results:
                subject = result.exam_subject.subject
                exam_level = result.cbc_level

                strands = Strand.objects.filter(
                    subject=subject,
                    subject__tenant=tenant,
                ).order_by('order').prefetch_related('sub_strands__outcomes')

                if not strands.exists():
                    continue

                strand_levels = assign_strand_levels(
                    exam_level=exam_level,
                    strands=list(strands),
                )

                for strand in strands:
                    strand_level = strand_levels.get(strand.id, exam_level)

                    for sub_strand in strand.sub_strands.order_by('order').prefetch_related('outcomes'):
                        outcomes = list(sub_strand.outcomes.order_by('order'))
                        outcome_levels = assign_outcome_levels(
                            strand_level=strand_level,
                            outcomes=outcomes,
                        )

                        for outcome in outcomes:
                            outcome_level = outcome_levels.get(outcome.id, strand_level)

                            exists = CBCGrade.objects.filter(
                                tenant=tenant,
                                student=result.student,
                                learning_outcome=outcome,
                                term=exam.term,
                                academic_year=exam.academic_year,
                            ).exists()

                            if exists:
                                total_skipped += 1
                                continue

                            pct = result.percentage
                            CBCGrade.objects.create(
                                tenant=tenant,
                                student=result.student,
                                learning_outcome=outcome,
                                term=exam.term,
                                academic_year=exam.academic_year,
                                level=outcome_level,
                                remarks=(
                                    f'Auto-filled from '
                                    f'{exam.get_exam_type_display()}'
                                    f' - {subject.name}: '
                                    f'{result.marks}/'
                                    f'{result.exam_subject.total_marks}'
                                    f' ({pct:.1f}%) -> '
                                    f'{exam_level} overall, '
                                    f'{strand.name}: {strand_level}'
                                ),
                                assessed_by=request.user,
                            )
                            total_synced += 1

        ExamCBCSync.objects.create(
            tenant=tenant,
            exam=exam,
            synced_by=request.user,
            records_synced=total_synced,
            records_skipped=total_skipped,
        )

        return Response({
            'synced': total_synced,
            'skipped': total_skipped,
            'message': (
                f'{total_synced} CBC grades created '
                f'with realistic strand variation, '
                f'{total_skipped} existing grades preserved.'
            ),
        })

    @action(detail=True, methods=['get'], permission_classes=[IsTeacherOrAdmin], url_path='marks-sheet')
    def marks_sheet(self, request, pk=None):
        exam = self.get_object()
        tenant = request.user.tenant
        students = Student.objects.filter(tenant=tenant, classroom=exam.classroom, is_active=True).order_by('last_name', 'first_name')
        exam_subjects = exam.exam_subjects.select_related('subject').all()
        if _is_teacher(request.user):
            exam_subjects = exam_subjects.filter(teacher=request.user)
        existing = ExamResult.objects.filter(tenant=tenant, exam_subject__exam=exam)
        if _is_teacher(request.user):
            existing = existing.filter(exam_subject__teacher=request.user)
        result_map = {
            (r.student_id, r.exam_subject_id): {
                'result_id': str(r.id),
                'marks': str(r.marks),
                'percentage': str(r.percentage),
                'cbc_level': r.cbc_level,
                'is_overridden': r.is_overridden,
                'override_reason': r.override_reason,
            }
            for r in existing
        }
        student_list = list(students)
        subject_list = list(exam_subjects)

        return Response({
            'exam': ExamSetupSerializer(exam).data,
            'students': [
                {'id': s.id, 'name': s.get_full_name(), 'admission_number': s.admission_number}
                for s in student_list
            ],
            'exam_subjects': [
                {
                    'id': es.id,
                    'subject_id': es.subject.id,
                    'subject_name': es.subject.name,
                    'subject_code': es.subject.code,
                    'total_marks': es.total_marks,
                }
                for es in subject_list
            ],
            'results': {
                f'{student.id}_{exam_subject.id}': result_map.get((student.id, exam_subject.id))
                for student in student_list
                for exam_subject in subject_list
            },
        })

    @action(detail=True, methods=['get'], permission_classes=[IsTeacherOrAdmin], url_path='sync-history')
    def sync_history(self, request, pk=None):
        exam = self.get_object()
        syncs = ExamCBCSync.objects.filter(tenant=request.user.tenant, exam=exam).order_by('-synced_at')
        return Response(ExamCBCSyncSerializer(syncs, many=True).data)


class ExamResultViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = ExamResult.objects.select_related(
        'student', 'student__primary_guardian', 'exam_subject__subject',
        'exam_subject__exam', 'entered_by',
    ).order_by('-entered_at', 'student__last_name', 'student__first_name')
    serializer_class = ExamResultSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['exam_subject', 'exam_subject__exam', 'cbc_level', 'is_overridden']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(
                exam_subject__exam__classroom_id__in=_teacher_classroom_ids(self.request.user),
                exam_subject__teacher=self.request.user,
            )
        if _is_parent(self.request.user):
            qs = qs.filter(student__primary_guardian__user=self.request.user)
        return qs

    def get_permissions(self):
        if self.action == 'student_results':
            return [CanViewReportCard()]
        if self.action in ['destroy']:
            return [IsAdminUser()]
        return [IsTeacherOrAdmin()]

    def perform_create(self, serializer):
        self._validate_exam_result(serializer.validated_data)
        serializer.save(tenant=self.request.user.tenant, entered_by=self.request.user)

    def perform_update(self, serializer):
        data = {
            'exam_subject': serializer.validated_data.get('exam_subject', serializer.instance.exam_subject),
            'student': serializer.validated_data.get('student', serializer.instance.student),
        }
        self._validate_exam_result(data)
        serializer.save(entered_by=self.request.user)

    def _validate_exam_result(self, data):
        exam_subject = data['exam_subject']
        student = data['student']
        if exam_subject.tenant_id != self.request.user.tenant_id or student.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Exam subject and student must belong to your school.')
        if student.classroom_id != exam_subject.exam.classroom_id:
            raise ValidationError('Student must be in the exam classroom.')
        if _is_teacher(self.request.user) and exam_subject.teacher_id != self.request.user.id:
            raise PermissionDenied('You can only enter marks for your assigned exam subjects.')

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk_enter(self, request):
        serializer = BulkExamResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant = request.user.tenant
        exam_subject = data['exam_subject']

        if exam_subject.tenant_id != tenant.id:
            raise ValidationError({'exam_subject': 'Exam subject not found in this school.'})
        if _is_teacher(request.user) and exam_subject.teacher_id != request.user.id:
            raise PermissionDenied('You can only enter marks for your assigned exam subjects.')

        created = 0
        updated = 0
        errors = []
        config = ExamConfig.get_for_tenant(tenant)

        with transaction.atomic():
            for entry in data['results']:
                student_id = entry.get('student_id')
                marks = entry.get('marks')
                is_overridden = entry.get('is_overridden', False)
                override_reason = entry.get('override_reason', '')
                cbc_level_override = entry.get('cbc_level')
                if student_id is None or marks is None:
                    errors.append(f'Missing student_id or marks: {entry}')
                    continue
                marks = Decimal(str(marks))
                student = Student.objects.filter(id=student_id, tenant=tenant, classroom=exam_subject.exam.classroom).first()
                if not student:
                    errors.append(f'Student {student_id} not found in exam class')
                    continue
                if marks < 0 or marks > exam_subject.total_marks:
                    errors.append(f'Invalid marks {marks} for student {student_id} - must be 0-{exam_subject.total_marks}')
                    continue
                computed_level = config.compute_level(marks, exam_subject.total_marks)
                final_level = cbc_level_override if is_overridden and cbc_level_override else computed_level
                pct = (marks / Decimal(str(exam_subject.total_marks))) * 100
                _, created_flag = ExamResult.objects.update_or_create(
                    tenant=tenant,
                    exam_subject=exam_subject,
                    student=student,
                    defaults={
                        'marks': marks,
                        'percentage': pct,
                        'cbc_level': final_level,
                        'is_overridden': is_overridden,
                        'override_reason': override_reason,
                        'entered_by': request.user,
                    },
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1

        return Response({'created': created, 'updated': updated, 'errors': errors, 'total': created + updated}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='import-csv', parser_classes=[MultiPartParser])
    def import_csv(self, request):
        file = request.FILES.get('file')
        exam_setup_id = request.data.get('exam_setup')
        if not file or not exam_setup_id:
            return Response({'error': 'file and exam_setup required'}, status=status.HTTP_400_BAD_REQUEST)
        tenant = request.user.tenant
        exam = ExamSetup.objects.filter(id=exam_setup_id, tenant=tenant).first()
        if not exam:
            return Response({'error': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        config = ExamConfig.get_for_tenant(tenant)
        created = 0
        updated = 0
        errors = []
        reader = csv.DictReader(io.StringIO(file.read().decode('utf-8')))

        with transaction.atomic():
            for i, row in enumerate(reader, start=2):
                adm = row.get('admission_number', '').strip()
                subject_code = row.get('subject_code', '').strip().upper()
                marks_str = row.get('marks', '').strip()
                if not adm or not subject_code or not marks_str:
                    errors.append(f'Row {i}: missing fields')
                    continue
                try:
                    marks = Decimal(marks_str)
                except Exception:
                    errors.append(f'Row {i}: invalid marks "{marks_str}"')
                    continue
                student = Student.objects.filter(tenant=tenant, admission_number=adm, classroom=exam.classroom).first()
                if not student:
                    errors.append(f'Row {i}: student {adm} not found in exam class')
                    continue
                exam_subject = ExamSubject.objects.filter(exam=exam, subject__code=subject_code, tenant=tenant).first()
                if not exam_subject:
                    errors.append(f'Row {i}: subject {subject_code} not in this exam')
                    continue
                if _is_teacher(request.user) and exam_subject.teacher_id != request.user.id:
                    errors.append(f'Row {i}: subject {subject_code} is not assigned to you')
                    continue
                if marks < 0 or marks > exam_subject.total_marks:
                    errors.append(f'Row {i}: marks {marks} out of range (0-{exam_subject.total_marks})')
                    continue
                pct = (marks / Decimal(str(exam_subject.total_marks))) * 100
                level = config.compute_level(marks, exam_subject.total_marks)
                _, created_flag = ExamResult.objects.update_or_create(
                    tenant=tenant,
                    exam_subject=exam_subject,
                    student=student,
                    defaults={
                        'marks': marks,
                        'percentage': pct,
                        'cbc_level': level,
                        'is_overridden': False,
                        'override_reason': '',
                        'entered_by': request.user,
                    },
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1

        return Response({'created': created, 'updated': updated, 'errors': errors, 'total_rows_processed': created + updated + len(errors)})

    @action(detail=False, methods=['get'], url_path='student-results')
    def student_results(self, request):
        student_id = request.query_params.get('student')
        if not student_id:
            return Response({'error': 'student param required'}, status=status.HTTP_400_BAD_REQUEST)
        _validate_student_for_user(request.user, student_id)
        qs = self.get_queryset().filter(student_id=student_id)
        term = request.query_params.get('term')
        year = request.query_params.get('academic_year')
        if term:
            qs = qs.filter(exam_subject__exam__term=term)
        if year:
            qs = qs.filter(exam_subject__exam__academic_year=int(year))
        return Response(ExamResultSerializer(qs, many=True).data)


class NationalExamSessionViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = NationalExamSession.objects.select_related('classroom', 'created_by').prefetch_related('candidates').order_by('-academic_year', 'name', 'classroom__name')
    serializer_class = NationalExamSessionSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'academic_year', 'classroom']

    def perform_create(self, serializer):
        classroom = serializer.validated_data['classroom']
        if classroom.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom must belong to your school.')
        serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='register-class')
    def register_class(self, request, pk=None):
        session = self.get_object()
        tenant = request.user.tenant
        students = Student.objects.filter(tenant=tenant, classroom=session.classroom, is_active=True)
        created = 0
        skipped = 0
        with transaction.atomic():
            for student in students:
                _, created_flag = NationalExamCandidate.objects.get_or_create(
                    tenant=tenant,
                    session=session,
                    student=student,
                    defaults={'is_registered': True},
                )
                if created_flag:
                    created += 1
                else:
                    skipped += 1
        return Response({'registered': created, 'already_existed': skipped})

    @action(detail=True, methods=['get'], url_path='download-csv')
    def download_csv(self, request, pk=None):
        session = self.get_object()
        tenant = request.user.tenant

        subject_ids = ClassSubjectAssignment.objects.filter(
            tenant=tenant,
            classroom=session.classroom,
            academic_year=session.academic_year,
        ).values_list('subject_id', flat=True).distinct()

        subjects = Subject.objects.filter(tenant=tenant, is_active=True)
        if subject_ids:
            subjects = subjects.filter(id__in=subject_ids)
        elif session.classroom.grade_level:
            subjects = subjects.filter(grade_levels__contains=[session.classroom.grade_level])

        subjects = subjects.order_by('order', 'name')
        candidates = NationalExamCandidate.objects.filter(
            tenant=tenant,
            session=session,
        ).select_related('student').order_by('student__last_name', 'student__first_name')

        response = HttpResponse(content_type='text/csv')
        filename = f'national_exam_{session.name}_{session.academic_year}_template.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        subject_headers = [subject.code for subject in subjects]
        writer.writerow([
            'admission_number', 'student_name', 'index_number',
            *subject_headers,
        ])

        for candidate in candidates:
            writer.writerow([
                candidate.student.admission_number,
                candidate.student.get_full_name(),
                candidate.index_number,
                *(['' for _ in subject_headers]),
            ])

        return response

    @action(detail=True, methods=['post'], url_path='import-csv', parser_classes=[MultiPartParser])
    def import_csv(self, request, pk=None):
        session = self.get_object()
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'file required'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = request.user.tenant
        subject_ids = ClassSubjectAssignment.objects.filter(
            tenant=tenant,
            classroom=session.classroom,
            academic_year=session.academic_year,
        ).values_list('subject_id', flat=True).distinct()

        subjects = Subject.objects.filter(tenant=tenant, is_active=True)
        if subject_ids:
            subjects = subjects.filter(id__in=subject_ids)
        elif session.classroom.grade_level:
            subjects = subjects.filter(grade_levels__contains=[session.classroom.grade_level])

        subjects = subjects.order_by('order', 'name')
        reader = csv.DictReader(io.StringIO(file.read().decode('utf-8')))
        created = 0
        updated = 0
        errors = []

        subject_codes = {subject.code: subject for subject in subjects}

        with transaction.atomic():
            for i, row in enumerate(reader, start=2):
                admission_number = row.get('admission_number', '').strip()
                index_number = row.get('index_number', '').strip()

                if not admission_number:
                    errors.append(f'Row {i}: missing admission_number')
                    continue

                candidate = NationalExamCandidate.objects.filter(
                    tenant=tenant,
                    session=session,
                    student__admission_number=admission_number,
                ).select_related('student').first()
                if not candidate:
                    errors.append(f'Row {i}: candidate {admission_number} not found in this session')
                    continue

                if index_number and candidate.index_number != index_number:
                    candidate.index_number = index_number
                    candidate.save(update_fields=['index_number'])

                if 'subject_code' in row:
                    subject_code = row.get('subject_code', '').strip().upper()
                    marks_str = row.get('marks', '').strip()
                    total_marks_str = row.get('total_marks', '').strip()
                    grade = row.get('grade', '').strip().upper()
                    remarks = row.get('remarks', '').strip()

                    if not subject_code:
                        errors.append(f'Row {i}: missing subject_code')
                        continue

                    subject = Subject.objects.filter(tenant=tenant, code=subject_code).first()
                    if not subject:
                        errors.append(f'Row {i}: subject {subject_code} not found')
                        continue

                    total_marks = 100
                    if total_marks_str:
                        try:
                            total_marks = int(total_marks_str)
                        except Exception:
                            errors.append(f'Row {i}: invalid total_marks "{total_marks_str}"')
                            continue

                    marks = None
                    if marks_str:
                        try:
                            marks = Decimal(marks_str)
                        except Exception:
                            errors.append(f'Row {i}: invalid marks "{marks_str}"')
                            continue
                        if marks < 0 or marks > total_marks:
                            errors.append(f'Row {i}: marks {marks} out of range (0-{total_marks})')
                            continue
                    elif not grade:
                        errors.append(f'Row {i}: missing marks or grade')
                        continue

                    _, created_flag = NationalExamResult.objects.update_or_create(
                        tenant=tenant,
                        candidate=candidate,
                        subject=subject,
                        defaults={
                            'marks': marks,
                            'total_marks': total_marks,
                            'grade': grade,
                            'remarks': remarks,
                        },
                    )
                    if created_flag:
                        created += 1
                    else:
                        updated += 1
                    continue

                for subject_code, subject in subject_codes.items():
                    marks_str = str(row.get(subject_code, '')).strip()
                    if not marks_str:
                        continue
                    try:
                        marks = Decimal(marks_str)
                    except Exception:
                        errors.append(f'Row {i}: invalid marks "{marks_str}" for {subject_code}')
                        continue
                    total_marks = 100
                    if marks < 0 or marks > total_marks:
                        errors.append(f'Row {i}: marks {marks} out of range (0-{total_marks}) for {subject_code}')
                        continue

                    _, created_flag = NationalExamResult.objects.update_or_create(
                        tenant=tenant,
                        candidate=candidate,
                        subject=subject,
                        defaults={
                            'marks': marks,
                            'total_marks': total_marks,
                            'grade': '',
                            'remarks': '',
                        },
                    )
                    if created_flag:
                        created += 1
                    else:
                        updated += 1

        if created or updated:
            NationalExamSession.objects.filter(id=session.id).update(is_results_entered=True)

        return Response({
            'created': created,
            'updated': updated,
            'errors': errors,
            'total_rows_processed': created + updated + len(errors),
        })


class NationalExamCandidateViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = NationalExamCandidate.objects.select_related('student', 'session', 'student__classroom').order_by('student__last_name', 'student__first_name')
    serializer_class = NationalExamCandidateSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['session', 'is_registered', 'registration_confirmed']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number', 'index_number']

    def perform_create(self, serializer):
        session = serializer.validated_data['session']
        student = serializer.validated_data['student']
        if session.tenant_id != self.request.user.tenant_id or student.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Session and student must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)

    def perform_update(self, serializer):
        session = serializer.validated_data.get('session', serializer.instance.session)
        student = serializer.validated_data.get('student', serializer.instance.student)
        if session.tenant_id != self.request.user.tenant_id or student.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Session and student must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=False, methods=['post'], url_path='bulk-update-index')
    def bulk_update_index(self, request):
        updates = request.data.get('updates', [])
        updated = 0
        errors = []
        with transaction.atomic():
            for entry in updates:
                candidate_id = entry.get('candidate_id')
                index = entry.get('index_number', '').strip()
                if not candidate_id or not index:
                    errors.append(f'Missing candidate_id or index_number: {entry}')
                    continue
                count = NationalExamCandidate.objects.filter(id=candidate_id, tenant=request.user.tenant).update(index_number=index)
                if count:
                    updated += 1
                else:
                    errors.append(f'Candidate {candidate_id} not found')
        return Response({'updated': updated, 'errors': errors})


class NationalExamResultViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = NationalExamResult.objects.select_related(
        'candidate__student', 'candidate__student__primary_guardian', 'candidate__session', 'subject',
    ).order_by('candidate__student__last_name', 'candidate__student__first_name', 'subject__name')
    serializer_class = NationalExamResultSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['candidate', 'subject', 'grade']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(candidate__session__classroom_id__in=_teacher_classroom_ids(self.request.user))
        if _is_parent(self.request.user):
            qs = qs.filter(candidate__student__primary_guardian__user=self.request.user)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [CanViewExamResult()]

    def perform_create(self, serializer):
        candidate = serializer.validated_data['candidate']
        subject = serializer.validated_data['subject']
        if candidate.tenant_id != self.request.user.tenant_id or subject.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Candidate and subject must belong to your school.')
        result = serializer.save(tenant=self.request.user.tenant)
        session = result.candidate.session
        if not session.is_results_entered:
            NationalExamSession.objects.filter(id=session.id).update(is_results_entered=True)


class AttendanceSessionViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = AttendanceSession.objects.select_related('classroom', 'subject', 'teacher').prefetch_related(
        'records__student'
    ).order_by('-date', 'classroom__name', 'session_type')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['classroom', 'date', 'session_type', 'term', 'academic_year', 'is_locked']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(classroom_id__in=_teacher_classroom_ids(self.request.user))
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return AttendanceSessionListSerializer
        return AttendanceSessionSerializer

    def get_permissions(self):
        if self.action in ['lock', 'destroy']:
            return [IsAdminUser()]
        return [IsTeacherOrAdmin()]

    def perform_create(self, serializer):
        classroom = serializer.validated_data['classroom']
        subject = serializer.validated_data.get('subject')
        if classroom.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom must belong to your school.')
        if subject and subject.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Subject must belong to your school.')
        if _is_teacher(self.request.user):
            if classroom.id not in set(_teacher_classroom_ids(self.request.user)):
                raise PermissionDenied('You can only create sessions for your assigned classes.')
            if subject and subject.id not in set(_teacher_subject_ids(self.request.user)):
                raise PermissionDenied('You can only create lesson sessions for your assigned subjects.')
        serializer.save(tenant=self.request.user.tenant, teacher=self.request.user)

    def perform_update(self, serializer):
        classroom = serializer.validated_data.get('classroom', serializer.instance.classroom)
        subject = serializer.validated_data.get('subject', serializer.instance.subject)
        if classroom.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom must belong to your school.')
        if subject and subject.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Subject must belong to your school.')
        if _is_teacher(self.request.user):
            if classroom.id not in set(_teacher_classroom_ids(self.request.user)):
                raise PermissionDenied('You can only update sessions for your assigned classes.')
            if subject and subject.id not in set(_teacher_subject_ids(self.request.user)):
                raise PermissionDenied('You can only update lesson sessions for your assigned subjects.')
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=True, methods=['post'], url_path='mark')
    def mark(self, request, pk=None):
        session = self.get_object()
        if session.is_locked:
            return Response({'error': 'Session is locked and cannot be edited.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = MarkAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = request.user.tenant
        created = 0
        updated = 0
        errors = []

        with transaction.atomic():
            for record in serializer.validated_data['records']:
                student_id = record.get('student_id')
                att_status = record.get('status', 'P')
                remarks = record.get('remarks', '')

                if not student_id:
                    errors.append(f'Missing student_id: {record}')
                    continue
                if att_status not in AttendanceRecord.Status.values:
                    errors.append(f'Invalid status for student {student_id}: {att_status}')
                    continue

                student = Student.objects.filter(id=student_id, tenant=tenant, classroom=session.classroom).first()
                if not student:
                    errors.append(f'Student {student_id} not found in session classroom')
                    continue

                _, created_flag = AttendanceRecord.objects.update_or_create(
                    tenant=tenant,
                    session=session,
                    student=student,
                    defaults={'status': att_status, 'remarks': remarks},
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1

        return Response({'created': created, 'updated': updated, 'errors': errors, 'session_id': session.id})

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser], url_path='lock')
    def lock(self, request, pk=None):
        session = self.get_object()
        session.is_locked = True
        session.save(update_fields=['is_locked'])
        return Response({'detail': 'Session locked.'})

    @action(detail=False, methods=['get'], url_path='today')
    def today(self, request):
        qs = self.get_queryset().filter(date=timezone.localdate())
        serializer = AttendanceSessionListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='student-summary')
    def student_summary(self, request):
        student_id = request.query_params.get('student')
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')

        if not student_id:
            return Response({'error': 'student param required'}, status=status.HTTP_400_BAD_REQUEST)

        _validate_student_for_user(request.user, student_id)
        qs = AttendanceRecord.objects.filter(tenant=request.user.tenant, student_id=student_id)
        if term:
            qs = qs.filter(session__term=term)
        if academic_year:
            qs = qs.filter(session__academic_year=int(academic_year))

        total = qs.count()
        present = qs.filter(status='P').count()
        absent = qs.filter(status='A').count()
        late = qs.filter(status='L').count()
        excused = qs.filter(status='E').count()
        percentage = round((present / total * 100), 1) if total else 0

        return Response({
            'total_sessions': total,
            'present': present,
            'absent': absent,
            'late': late,
            'excused': excused,
            'attendance_percentage': percentage,
        })

    @action(detail=False, methods=['get'], url_path='class-summary')
    def class_summary(self, request):
        classroom_id = request.query_params.get('classroom')
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')

        if not classroom_id:
            return Response({'error': 'classroom param required'}, status=status.HTTP_400_BAD_REQUEST)
        if _is_teacher(request.user) and int(classroom_id) not in set(_teacher_classroom_ids(request.user)):
            raise PermissionDenied('You can only access your assigned classes.')

        students = Student.objects.filter(
            tenant=request.user.tenant,
            classroom_id=classroom_id,
            is_active=True,
        ).order_by('last_name', 'first_name')

        result = []
        for student in students:
            qs = AttendanceRecord.objects.filter(tenant=request.user.tenant, student=student)
            if term:
                qs = qs.filter(session__term=term)
            if academic_year:
                qs = qs.filter(session__academic_year=int(academic_year))
            total = qs.count()
            present = qs.filter(status='P').count()
            absent = qs.filter(status='A').count()
            late = qs.filter(status='L').count()
            percentage = round(present / total * 100, 1) if total else 0

            result.append({
                'student_id': student.id,
                'student_name': student.get_full_name(),
                'admission_number': student.admission_number,
                'total': total,
                'present': present,
                'absent': absent,
                'late': late,
                'percentage': percentage,
            })

        return Response(result)


class ClassTimetableViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = ClassTimetable.objects.select_related('classroom', 'uploaded_by').order_by(
        '-academic_year', 'term', 'classroom__name'
    )
    serializer_class = ClassTimetableSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['classroom', 'term', 'academic_year']
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(classroom_id__in=_teacher_classroom_ids(self.request.user))
        if _is_parent(self.request.user):
            student_classrooms = Student.objects.filter(
                tenant=self.request.user.tenant,
                primary_guardian__user=self.request.user,
                is_active=True,
            ).values_list('classroom_id', flat=True)
            qs = qs.filter(classroom_id__in=student_classrooms)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [CanViewTimetable()]

    def perform_create(self, serializer):
        classroom = serializer.validated_data['classroom']
        if classroom.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom must belong to your school.')
        serializer.save(tenant=self.request.user.tenant, uploaded_by=self.request.user)

    def perform_update(self, serializer):
        classroom = serializer.validated_data.get('classroom', serializer.instance.classroom)
        if classroom.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom must belong to your school.')
        serializer.save(tenant=self.request.user.tenant)


class CoCurricularActivityViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = CoCurricularActivity.objects.order_by('category', 'name')
    serializer_class = CoCurricularActivitySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'is_active']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsTeacherOrAdmin()]


class StudentCoCurricularViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = StudentCoCurricular.objects.select_related('student', 'activity').order_by(
        '-academic_year', 'term', 'student__last_name', 'student__first_name'
    )
    serializer_class = StudentCoCurricularSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'term', 'academic_year', 'activity']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(student__classroom_id__in=_teacher_classroom_ids(self.request.user))
        return qs

    def perform_create(self, serializer):
        student = serializer.validated_data['student']
        activity = serializer.validated_data['activity']
        if student.tenant_id != self.request.user.tenant_id or activity.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Student and activity must belong to your school.')
        if _is_teacher(self.request.user) and student.classroom_id not in set(_teacher_classroom_ids(self.request.user)):
            raise PermissionDenied('You can only record activities for your assigned classes.')
        serializer.save(tenant=self.request.user.tenant)

    def perform_update(self, serializer):
        student = serializer.validated_data.get('student', serializer.instance.student)
        activity = serializer.validated_data.get('activity', serializer.instance.activity)
        if student.tenant_id != self.request.user.tenant_id or activity.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Student and activity must belong to your school.')
        if _is_teacher(self.request.user) and student.classroom_id not in set(_teacher_classroom_ids(self.request.user)):
            raise PermissionDenied('You can only update activities for your assigned classes.')
        serializer.save(tenant=self.request.user.tenant)


class ReportCardViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = ReportCard.objects.select_related(
        'student', 'student__primary_guardian', 'classroom', 'generated_by'
    ).order_by('-academic_year', '-term', 'student__last_name', 'student__first_name')
    serializer_class = ReportCardSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['classroom', 'term', 'academic_year', 'status', 'report_type']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            qs = qs.filter(classroom_id__in=_teacher_classroom_ids(self.request.user))
        if _is_parent(self.request.user):
            qs = qs.filter(student__primary_guardian__user=self.request.user, status='published')
        return qs

    def get_permissions(self):
        if self.action == 'publish':
            return [IsAdminUser()]
        if self.action in ['generate', 'generate_annual']:
            return [IsTeacherOrAdmin()]
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTeacherOrAdmin()]
        return [CanViewReportCard()]

    def perform_create(self, serializer):
        student = serializer.validated_data['student']
        classroom = serializer.validated_data.get('classroom')
        if student.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Student must belong to your school.')
        if classroom and classroom.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom must belong to your school.')
        if _is_teacher(self.request.user) and student.classroom_id not in set(_teacher_classroom_ids(self.request.user)):
            raise PermissionDenied('You can only create report cards for your assigned classes.')
        serializer.save(tenant=self.request.user.tenant, generated_by=self.request.user)

    def perform_update(self, serializer):
        student = serializer.validated_data.get('student', serializer.instance.student)
        classroom = serializer.validated_data.get('classroom', serializer.instance.classroom)
        if student.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Student must belong to your school.')
        if classroom and classroom.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom must belong to your school.')
        if _is_teacher(self.request.user) and student.classroom_id not in set(_teacher_classroom_ids(self.request.user)):
            raise PermissionDenied('You can only update report cards for your assigned classes.')
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        serializer = GenerateReportCardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant = request.user.tenant
        classroom = data['classroom']

        if classroom.tenant_id != tenant.id:
            raise ValidationError({'classroom': 'Classroom not found in this school.'})
        if _is_teacher(request.user) and classroom.id not in set(_teacher_classroom_ids(request.user)):
            raise PermissionDenied('You can only generate reports for your assigned classes.')

        students = Student.objects.filter(tenant=tenant, classroom=classroom, is_active=True)
        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for student in students:
                att_records = AttendanceRecord.objects.filter(
                    tenant=tenant,
                    student=student,
                    session__term=data['term'],
                    session__academic_year=data['academic_year'],
                    session__session_type='daily',
                )
                total = att_records.count()
                present = att_records.filter(status='P').count()
                absent = att_records.filter(status='A').count()
                late = att_records.filter(status='L').count()

                _, created = ReportCard.objects.get_or_create(
                    tenant=tenant,
                    student=student,
                    term=data['term'],
                    academic_year=data['academic_year'],
                    report_type='termly',
                    defaults={
                        'classroom': classroom,
                        'days_school_open': total,
                        'days_present': present,
                        'days_absent': absent,
                        'days_late': late,
                        'closing_date': data.get('closing_date'),
                        'next_term_opening_date': data.get('next_term_opening_date'),
                        'status': 'draft',
                        'generated_by': request.user,
                    },
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        return Response({
            'created': created_count,
            'skipped': skipped_count,
            'message': f'{created_count} report cards generated, {skipped_count} already existed.',
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='generate-annual')
    def generate_annual(self, request):
        classroom_id = request.data.get('classroom')
        academic_year = request.data.get('academic_year')

        if not classroom_id or not academic_year:
            return Response({'error': 'classroom and academic_year required'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = request.user.tenant
        classroom = Classroom.objects.filter(id=classroom_id, tenant=tenant).first()
        if not classroom:
            raise ValidationError({'classroom': 'Classroom not found in this school.'})
        if _is_teacher(request.user) and classroom.id not in set(_teacher_classroom_ids(request.user)):
            raise PermissionDenied('You can only generate reports for your assigned classes.')

        students = Student.objects.filter(tenant=tenant, classroom=classroom, is_active=True)
        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for student in students:
                att_records = AttendanceRecord.objects.filter(
                    tenant=tenant,
                    student=student,
                    session__academic_year=int(academic_year),
                    session__session_type='daily',
                )
                total = att_records.count()
                present = att_records.filter(status='P').count()
                absent = att_records.filter(status='A').count()
                late = att_records.filter(status='L').count()

                _, created = ReportCard.objects.get_or_create(
                    tenant=tenant,
                    student=student,
                    term='',
                    academic_year=int(academic_year),
                    report_type='annual',
                    defaults={
                        'classroom': classroom,
                        'days_school_open': total,
                        'days_present': present,
                        'days_absent': absent,
                        'days_late': late,
                        'status': 'draft',
                        'generated_by': request.user,
                    },
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        return Response({'created': created_count, 'skipped': skipped_count}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser], url_path='publish')
    def publish(self, request, pk=None):
        report_card = self.get_object()
        if report_card.status == 'published':
            return Response({'detail': 'Already published.'}, status=status.HTTP_200_OK)
        report_card.status = 'published'
        report_card.published_at = timezone.now()
        report_card.save(update_fields=['status', 'published_at'])
        return Response(ReportCardSerializer(report_card, context={'request': request}).data)

    @action(detail=True, methods=['get'], permission_classes=[CanViewReportCard], url_path='pdf')
    def pdf(self, request, pk=None):
        report_card = self.get_object()
        tenant = request.user.tenant

        if _is_parent(request.user):
            if not user_owns_student(request.user, report_card.student):
                return Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
            if report_card.status != 'published':
                return Response({'error': 'Report card not yet published.'}, status=status.HTTP_403_FORBIDDEN)

        student = report_card.student
        classroom = report_card.classroom
        grades = CBCGrade.objects.filter(
            tenant=tenant,
            student=student,
            term=report_card.term,
            academic_year=report_card.academic_year,
        ).select_related('learning_outcome__sub_strand__strand__subject').order_by(
            'learning_outcome__sub_strand__strand__subject__order',
            'learning_outcome__sub_strand__strand__order',
            'learning_outcome__sub_strand__order',
            'learning_outcome__order',
        )
        co_curricular = StudentCoCurricular.objects.filter(
            tenant=tenant,
            student=student,
            term=report_card.term,
            academic_year=report_card.academic_year,
        ).select_related('activity')

        response = HttpResponse(content_type='application/pdf')
        filename = f'report_card_{student.admission_number}_{report_card.term}_{report_card.academic_year}.pdf'
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader, simpleSplit
        from reportlab.pdfgen import canvas

        pdf = canvas.Canvas(response, pagesize=A4)
        page_width, page_height = A4
        margin_x = 40
        y = page_height - 40

        if tenant.logo:
            try:
                pdf.drawImage(ImageReader(tenant.logo.path), margin_x, y - 55, width=55, height=55, preserveAspectRatio=True)
            except Exception:
                pass

        pdf.setFont('Helvetica-Bold', 14)
        pdf.drawCentredString(page_width / 2, y - 20, tenant.name.upper())
        pdf.setFont('Helvetica-Bold', 11)
        pdf.drawCentredString(page_width / 2, y - 36, 'CBC LEARNER PROGRESS REPORT')
        pdf.setFont('Helvetica', 9)
        pdf.drawCentredString(page_width / 2, y - 50, f'{report_card.term or report_card.get_report_type_display()} {report_card.academic_year}')

        y -= 70
        pdf.line(margin_x, y, page_width - margin_x, y)
        y -= 14

        pdf.setFont('Helvetica-Bold', 9)
        pdf.drawString(margin_x, y, f'Name: {student.get_full_name()}')
        pdf.drawString(page_width / 2, y, f'Adm No: {student.admission_number}')
        y -= 14
        pdf.drawString(margin_x, y, f'Class: {classroom or "-"}')
        pdf.drawString(page_width / 2, y, f'Stream: {classroom.stream if classroom else "-"}')
        y -= 10
        pdf.line(margin_x, y, page_width - margin_x, y)
        y -= 14

        def wrap_text(text, width, font_name, font_size):
            if not text:
                return ['']
            return simpleSplit(str(text), font_name, font_size, width) or ['']

        def draw_learning_header(y_pos, continued=False):
            title = 'LEARNING AREA PERFORMANCE'
            if continued:
                title += ' (cont.)'
            pdf.setFont('Helvetica-Bold', 10)
            pdf.drawString(margin_x, y_pos, title)
            y_pos -= 14

            pdf.setFont('Helvetica-Bold', 8)
            pdf.drawString(col_subject, y_pos, 'Subject')
            pdf.drawString(col_strand, y_pos, 'Strand')
            pdf.drawString(col_substrand, y_pos, 'Sub-Strand')
            pdf.drawString(col_outcome, y_pos, 'Outcome')
            pdf.drawString(col_level, y_pos, 'Level')
            y_pos -= 10
            pdf.line(margin_x, y_pos, page_width - margin_x, y_pos)
            return y_pos - 12

        col_subject = margin_x
        col_strand = col_subject + 80
        col_substrand = col_strand + 90
        col_outcome = col_substrand + 100
        col_level = page_width - margin_x - 30
        width_subject = col_strand - col_subject - 4
        width_strand = col_substrand - col_strand - 4
        width_substrand = col_outcome - col_substrand - 4
        width_outcome = col_level - col_outcome - 8

        y = draw_learning_header(y, continued=False)

        row_font = 'Helvetica'
        row_size = 7
        row_line_height = 9
        pdf.setFont(row_font, row_size)

        current_subject = None
        current_strand = None
        current_substrand = None
        level_colors = {
            'EE': colors.HexColor('#16a34a'),
            'ME': colors.HexColor('#2563eb'),
            'AE': colors.HexColor('#ea580c'),
            'BE': colors.HexColor('#dc2626'),
        }

        for grade in grades:
            outcome = grade.learning_outcome
            sub_strand = outcome.sub_strand
            strand = sub_strand.strand
            subject = strand.subject

            subject_label = subject.name if subject.name != current_subject else ''
            strand_label = strand.name if strand.name != current_strand else ''
            sub_strand_label = sub_strand.name if sub_strand.name != current_substrand else ''

            subject_lines = wrap_text(subject_label, width_subject, row_font, row_size)
            strand_lines = wrap_text(strand_label, width_strand, row_font, row_size)
            substrand_lines = wrap_text(sub_strand_label, width_substrand, row_font, row_size)
            outcome_lines = wrap_text(outcome.description, width_outcome, row_font, row_size)

            row_lines = max(len(subject_lines), len(strand_lines), len(substrand_lines), len(outcome_lines), 1)
            row_height = row_lines * row_line_height

            if y - row_height < 80:
                pdf.showPage()
                y = page_height - 40
                current_subject = None
                current_strand = None
                current_substrand = None
                y = draw_learning_header(y, continued=True)
                pdf.setFont(row_font, row_size)

            for i in range(row_lines):
                line_y = y - i * row_line_height
                if i < len(subject_lines):
                    pdf.drawString(col_subject, line_y, subject_lines[i])
                if i < len(strand_lines):
                    pdf.drawString(col_strand, line_y, strand_lines[i])
                if i < len(substrand_lines):
                    pdf.drawString(col_substrand, line_y, substrand_lines[i])
                if i < len(outcome_lines):
                    pdf.drawString(col_outcome, line_y, outcome_lines[i])

            pdf.setFillColor(level_colors.get(grade.level, colors.black))
            pdf.setFont('Helvetica-Bold', 8)
            pdf.drawString(col_level, y, grade.level)
            pdf.setFillColor(colors.black)
            pdf.setFont(row_font, row_size)

            y -= row_height
            current_subject = subject.name
            current_strand = strand.name
            current_substrand = sub_strand.name

        y -= 6
        pdf.line(margin_x, y, page_width - margin_x, y)
        y -= 14

        exam_results = ExamResult.objects.filter(
            tenant=tenant,
            student=student,
            exam_subject__exam__academic_year=report_card.academic_year,
        ).select_related(
            'exam_subject__exam', 'exam_subject__subject'
        ).order_by(
            'exam_subject__exam__start_date',
            'exam_subject__subject__order',
            'exam_subject__subject__name',
        )
        if report_card.term:
            exam_results = exam_results.filter(exam_subject__exam__term=report_card.term)

        if exam_results.exists():
            exam_groups = {}
            for result in exam_results:
                exam = result.exam_subject.exam
                exam_groups.setdefault(exam.id, {'exam': exam, 'results': []})['results'].append(result)

            if y < 120:
                pdf.showPage()
                y = page_height - 40

            pdf.setFont('Helvetica-Bold', 10)
            pdf.drawString(margin_x, y, 'EXAM RESULTS')
            y -= 14

            exam_subject_width = 210
            col_exam_subject = margin_x
            col_exam_marks = margin_x + 230
            col_exam_total = margin_x + 290
            col_exam_pct = margin_x + 350
            col_exam_level = margin_x + 410

            def draw_exam_header(y_pos, exam_title):
                pdf.setFont('Helvetica-Bold', 9)
                pdf.drawString(margin_x, y_pos, exam_title)
                y_pos -= 12
                pdf.setFont('Helvetica-Bold', 8)
                pdf.drawString(col_exam_subject, y_pos, 'Subject')
                pdf.drawString(col_exam_marks, y_pos, 'Marks')
                pdf.drawString(col_exam_total, y_pos, 'Total')
                pdf.drawString(col_exam_pct, y_pos, '%')
                pdf.drawString(col_exam_level, y_pos, 'Level')
                y_pos -= 10
                pdf.line(margin_x, y_pos, page_width - margin_x, y_pos)
                return y_pos - 12

            for group in exam_groups.values():
                exam = group['exam']
                exam_title = f"{exam.name} ({exam.get_exam_type_display()})"
                if y < 120:
                    pdf.showPage()
                    y = page_height - 40
                y = draw_exam_header(y, exam_title)
                pdf.setFont('Helvetica', 8)

                for result in group['results']:
                    subject_lines = wrap_text(
                        result.exam_subject.subject.name,
                        exam_subject_width,
                        'Helvetica',
                        8,
                    )
                    row_lines = max(len(subject_lines), 1)
                    row_height = row_lines * 10

                    if y - row_height < 80:
                        pdf.showPage()
                        y = page_height - 40
                        y = draw_exam_header(y, exam_title)
                        pdf.setFont('Helvetica', 8)

                    marks_label = f"{result.marks}" if result.marks is not None else '-'
                    total_label = f"{result.exam_subject.total_marks}"
                    pct_label = f"{float(result.percentage):.1f}" if result.marks is not None else '-'

                    for i in range(row_lines):
                        line_y = y - i * 10
                        if i < len(subject_lines):
                            pdf.drawString(col_exam_subject, line_y, subject_lines[i])
                    pdf.drawString(col_exam_marks, y, marks_label)
                    pdf.drawString(col_exam_total, y, total_label)
                    pdf.drawString(col_exam_pct, y, pct_label)
                    pdf.drawString(col_exam_level, y, result.cbc_level)
                    y -= row_height

                y -= 6
                pdf.line(margin_x, y, page_width - margin_x, y)
                y -= 14

        if y < 100:
            pdf.showPage()
            y = page_height - 40

        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(margin_x, y, 'ATTENDANCE')
        y -= 14
        pdf.setFont('Helvetica', 9)
        pdf.drawString(margin_x, y, f'Days School Open: {report_card.days_school_open}')
        pdf.drawString(page_width / 2, y, f'Days Present: {report_card.days_present}')
        y -= 12
        pdf.drawString(margin_x, y, f'Days Absent: {report_card.days_absent}')
        pdf.drawString(page_width / 2, y, f'Days Late: {report_card.days_late}')
        y -= 12
        percentage = round(report_card.days_present / report_card.days_school_open * 100, 1) if report_card.days_school_open else 0
        pdf.drawString(margin_x, y, f'Attendance: {percentage}%')
        y -= 10
        pdf.line(margin_x, y, page_width - margin_x, y)
        y -= 14

        if co_curricular.exists():
            pdf.setFont('Helvetica-Bold', 10)
            pdf.drawString(margin_x, y, 'CO-CURRICULAR ACTIVITIES')
            y -= 14
            pdf.setFont('Helvetica-Bold', 8)
            col_activity = margin_x
            col_category = margin_x + 170
            col_rating = margin_x + 300
            col_remarks = margin_x + 380
            width_activity = col_category - col_activity - 6
            width_remarks = page_width - margin_x - col_remarks
            pdf.drawString(col_activity, y, 'Activity')
            pdf.drawString(col_category, y, 'Category')
            pdf.drawString(col_rating, y, 'Rating')
            pdf.drawString(col_remarks, y, 'Remarks')
            y -= 12
            pdf.setFont('Helvetica', 8)
            for record in co_curricular:
                activity_lines = wrap_text(record.activity.name, width_activity, 'Helvetica', 8)
                remarks_lines = wrap_text(record.remarks, width_remarks, 'Helvetica', 8)
                row_lines = max(len(activity_lines), len(remarks_lines), 1)
                row_height = row_lines * 10
                if y - row_height < 80:
                    pdf.showPage()
                    y = page_height - 40
                    pdf.setFont('Helvetica-Bold', 10)
                    pdf.drawString(margin_x, y, 'CO-CURRICULAR ACTIVITIES (cont.)')
                    y -= 14
                    pdf.setFont('Helvetica-Bold', 8)
                    pdf.drawString(col_activity, y, 'Activity')
                    pdf.drawString(col_category, y, 'Category')
                    pdf.drawString(col_rating, y, 'Rating')
                    pdf.drawString(col_remarks, y, 'Remarks')
                    y -= 12
                    pdf.setFont('Helvetica', 8)
                for i in range(row_lines):
                    line_y = y - i * 10
                    if i < len(activity_lines):
                        pdf.drawString(col_activity, line_y, activity_lines[i])
                    if i == 0:
                        pdf.drawString(col_category, line_y, record.activity.get_category_display())
                        pdf.drawString(col_rating, line_y, record.get_rating_display())
                    if i < len(remarks_lines):
                        pdf.drawString(col_remarks, line_y, remarks_lines[i])
                y -= row_height
            y -= 4
            pdf.line(margin_x, y, page_width - margin_x, y)
            y -= 14

        if y < 120:
            pdf.showPage()
            y = page_height - 40

        conduct_labels = {1: 'Poor', 2: 'Fair', 3: 'Good', 4: 'Excellent'}
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(margin_x, y, 'CONDUCT')
        y -= 14
        pdf.setFont('Helvetica', 9)
        conduct_items = [
            ('Discipline', report_card.conduct_discipline),
            ('Respect', report_card.conduct_respect),
            ('Responsibility', report_card.conduct_responsibility),
            ('Punctuality', report_card.conduct_punctuality),
            ('Participation', report_card.conduct_participation),
        ]
        for i, (label, value) in enumerate(conduct_items):
            x = margin_x + (i % 2) * (page_width / 2 - 40)
            if i % 2 == 0 and i > 0:
                y -= 12
            pdf.drawString(x, y, f'{label}: {conduct_labels.get(value, value)}')
        y -= 16
        pdf.line(margin_x, y, page_width - margin_x, y)
        y -= 14

        pdf.setFont('Helvetica-Bold', 9)
        pdf.drawString(margin_x, y, 'Class Teacher Remarks:')
        pdf.setFont('Helvetica', 9)
        y -= 12
        teacher_lines = wrap_text(report_card.class_teacher_remarks or '-', page_width - (2 * margin_x), 'Helvetica', 9)
        for line in teacher_lines:
            if y < 80:
                pdf.showPage()
                y = page_height - 40
            pdf.drawString(margin_x, y, line)
            y -= 12
        y -= 4
        pdf.setFont('Helvetica-Bold', 9)
        pdf.drawString(margin_x, y, "Principal's Remarks:")
        pdf.setFont('Helvetica', 9)
        y -= 12
        principal_lines = wrap_text(report_card.principal_remarks or '-', page_width - (2 * margin_x), 'Helvetica', 9)
        for line in principal_lines:
            if y < 80:
                pdf.showPage()
                y = page_height - 40
            pdf.drawString(margin_x, y, line)
            y -= 12
        y -= 4
        pdf.line(margin_x, y, page_width - margin_x, y)
        y -= 14

        pdf.setFont('Helvetica', 9)
        if report_card.closing_date:
            pdf.drawString(margin_x, y, f'Closing Date: {report_card.closing_date}')
        if report_card.next_term_opening_date:
            pdf.drawString(page_width / 2, y, f'Next Term Opens: {report_card.next_term_opening_date}')
        y -= 20
        pdf.drawString(margin_x, y, 'Class Teacher: _____________')
        pdf.drawString(page_width / 2, y, 'Signature: _________________')
        y -= 16
        pdf.drawString(margin_x, y, 'Principal: _________________')
        pdf.drawString(page_width / 2, y, 'Signature: _________________')
        y -= 20
        pdf.setFont('Helvetica-Oblique', 7)
        pdf.drawCentredString(page_width / 2, y, f'Official Report Card - {tenant.name} - CBC Competency Based Assessment')
        pdf.showPage()
        pdf.save()
        return response

    @action(detail=False, methods=['get'], url_path='student/(?P<student_id>[^/.]+)')
    def student_report_cards(self, request, student_id=None):
        _validate_student_for_user(request.user, student_id)
        qs = self.get_queryset().filter(student_id=student_id).order_by('-academic_year', '-term')
        if _is_parent(request.user):
            qs = qs.filter(status='published')
        return Response(ReportCardSerializer(qs, many=True, context={'request': request}).data)
