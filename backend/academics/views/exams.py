"""Exam setup and exam result viewsets."""
import csv
import io
from decimal import Decimal

from django.db import transaction, IntegrityError, models
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from students.models import Student

from ..models import (
    CBCGrade,
    ClassSubjectAssignment,
    ExamCBCSync,
    ExamResult,
    ExamConfig,
    ExamSetup,
    ExamSubject,
    LearningOutcome,
    Strand,
)
from ..permissions import IsAdminUser, IsTeacherOrAdmin, CanViewReportCard
from ..serializers import (
    BulkExamResultSerializer,
    ExamCBCSyncSerializer,
    ExamResultSerializer,
    ExamSetupListSerializer,
    ExamSetupSerializer,
    ExamSubjectSerializer,
)
from .mixins import (
    TenantScopedMixin,
    _is_teacher,
    _is_parent,
    _teacher_classroom_ids,
    _teacher_subject_ids,
    _validate_student_for_user,
)


def _teacher_has_subject_assignment(user, exam_subject):
    """Check if teacher has a ClassSubjectAssignment for this exam's class+subject."""
    if not _is_teacher(user):
        return True
    return ClassSubjectAssignment.objects.filter(
        tenant=user.tenant,
        teacher=user,
        classroom=exam_subject.exam.classroom,
        subject=exam_subject.subject,
    ).exists()


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
        try:
            serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)
        except IntegrityError:
            raise ValidationError(
                'An exam with this name already exists for this class, term and academic year.'
            )

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
        from ..utils import assign_strand_levels, assign_outcome_levels

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
            # Check both explicit ExamSubject.teacher AND ClassSubjectAssignment
            exam_subjects = exam_subjects.filter(
                models.Q(teacher=request.user) |
                models.Q(
                    subject__assignments__teacher=request.user,
                    subject__assignments__classroom=exam.classroom,
                    subject__assignments__academic_year=exam.academic_year,
                    subject__assignments__term=exam.term,
                )
            ).distinct()
        existing = ExamResult.objects.filter(tenant=tenant, exam_subject__exam=exam)
        if _is_teacher(request.user):
            existing = existing.filter(
                models.Q(exam_subject__teacher=request.user) |
                models.Q(
                    exam_subject__subject__assignments__teacher=request.user,
                    exam_subject__subject__assignments__classroom=exam.classroom,
                    exam_subject__subject__assignments__academic_year=exam.academic_year,
                    exam_subject__subject__assignments__term=exam.term,
                )
            ).distinct()
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
            ).filter(
                models.Q(exam_subject__teacher=self.request.user) |
                models.Q(
                    exam_subject__subject__assignments__teacher=self.request.user,
                    exam_subject__subject__assignments__classroom=models.F('exam_subject__exam__classroom'),
                    exam_subject__subject__assignments__academic_year=models.F('exam_subject__exam__academic_year'),
                    exam_subject__subject__assignments__term=models.F('exam_subject__exam__term'),
                )
            ).distinct()
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
        if _is_teacher(self.request.user):
            # Check explicit ExamSubject.teacher first, then fall back to ClassSubjectAssignment
            if exam_subject.teacher_id == self.request.user.id:
                return
            if not _teacher_has_subject_assignment(self.request.user, exam_subject):
                raise PermissionDenied('You can only enter marks for your assigned exam subjects.')

    @action(detail=False, methods=['get'], url_path='student-results')
    def student_results(self, request):
        student_id = request.query_params.get('student')
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')

        if not student_id:
            return Response({'error': 'student param required'}, status=status.HTTP_400_BAD_REQUEST)

        _validate_student_for_user(request.user, student_id)
        qs = self.get_queryset().filter(student_id=student_id)
        if term:
            qs = qs.filter(exam_subject__exam__term=term)
        if academic_year:
            qs = qs.filter(exam_subject__exam__academic_year=int(academic_year))

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk_enter(self, request):
        serializer = BulkExamResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant = request.user.tenant
        exam_subject = data['exam_subject']

        if exam_subject.tenant_id != tenant.id:
            raise ValidationError({'exam_subject': 'Exam subject not found in this school.'})
        if _is_teacher(request.user):
            if exam_subject.teacher_id == request.user.id:
                pass  # OK - explicitly assigned
            elif not _teacher_has_subject_assignment(request.user, exam_subject):
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

        # Build subject lookup: code -> ExamSubject
        exam_subjects = {es.subject.code.upper(): es for es in exam.exam_subjects.all()}
        if not exam_subjects:
            return Response({'error': 'No subjects configured for this exam.'}, status=status.HTTP_400_BAD_REQUEST)

        config = ExamConfig.get_for_tenant(tenant)
        content = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))

        # Normalize headers
        fieldnames = [h.strip().upper() for h in (reader.fieldnames or [])]
        if 'ADMISSION_NUMBER' not in fieldnames:
            return Response({'error': 'CSV must have an admission_number column.'}, status=status.HTTP_400_BAD_REQUEST)

        # Map subject codes to column names (case-insensitive)
        # Explicitly skip non-subject columns like admission_number and name
        subject_code_map = {}
        for header in fieldnames:
            h_upper = header.upper()
            if h_upper in ('ADMISSION_NUMBER', 'NAME'):
                continue
            if h_upper in exam_subjects:
                subject_code_map[header] = h_upper

        if not subject_code_map:
            return Response(
                {'error': f'No valid subject columns found in CSV. Expected one of: {", ".join(sorted(exam_subjects.keys()))}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created = 0
        updated = 0
        errors = []

        with transaction.atomic():
            for i, raw_row in enumerate(reader, start=2):
                row = {k.strip().upper(): (v.strip() if v is not None else '') for k, v in raw_row.items()}
                adm = row.get('ADMISSION_NUMBER', '')
                if not adm:
                    errors.append({'row': i, 'message': 'Missing admission_number'})
                    continue

                student = Student.objects.filter(tenant=tenant, admission_number=adm, classroom=exam.classroom).first()
                if not student:
                    errors.append({'row': i, 'field': 'admission_number', 'message': f'Student {adm} not found in exam class'})
                    continue

                for col_name, subject_code in subject_code_map.items():
                    marks_str = row.get(subject_code, '')
                    if not marks_str:
                        continue  # skip empty cells

                    try:
                        marks = Decimal(marks_str)
                    except Exception:
                        errors.append({'row': i, 'field': subject_code, 'message': f'Invalid marks "{marks_str}"'})
                        continue

                    exam_subject = exam_subjects.get(subject_code)
                    if not exam_subject:
                        errors.append({'row': i, 'field': subject_code, 'message': f'Subject {subject_code} not in this exam'})
                        continue

                    if _is_teacher(request.user):
                        if exam_subject.teacher_id == request.user.id:
                            pass  # OK
                        elif not _teacher_has_subject_assignment(request.user, exam_subject):
                            errors.append({'row': i, 'field': subject_code, 'message': f'Subject {subject_code} is not assigned to you'})
                            continue

                    if marks < 0 or marks > exam_subject.total_marks:
                        errors.append({'row': i, 'field': subject_code, 'message': f'Marks {marks} out of range (0-{exam_subject.total_marks})'})
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

        return Response({
            'created': created,
            'updated': updated,
            'errors': errors,
            'total_rows_processed': created + updated + len(errors),
        })