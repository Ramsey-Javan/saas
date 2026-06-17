"""CBC grading and exam configuration viewsets."""
import csv
import io
from decimal import Decimal

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from students.models import Student

from ..models import CBCGrade, ExamConfig, LearningOutcome
from ..permissions import IsTeacherOrAdmin
from ..serializers import (
    BulkGradeSerializer,
    CBCGradeSerializer,
    ExamConfigSerializer,
)
from .mixins import (
    TenantScopedMixin,
    _is_teacher,
    _teacher_classroom_ids,
    _teacher_subject_ids,
    _validate_student_for_user,
)


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
