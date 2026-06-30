"""National exam session, candidate and result viewsets."""
import csv
import io
from decimal import Decimal

from django.db import transaction
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from students.models import Student

from ..models import (
    ClassSubjectAssignment,
    NationalExamCandidate,
    NationalExamResult,
    NationalExamSession,
    Subject,
)
from ..permissions import IsAdminUser, CanViewExamResult
from ..serializers import (
    NationalExamCandidateSerializer,
    NationalExamResultSerializer,
    NationalExamSessionSerializer,
)
from .mixins import (
    TenantScopedMixin,
    _is_teacher,
    _is_parent,
    _teacher_classroom_ids,
)


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
        if subject_ids.exists():
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
        # Get allowed subjects for this exam session
        subject_ids = ClassSubjectAssignment.objects.filter(
            tenant=tenant,
            classroom=session.classroom,
            academic_year=session.academic_year,
        ).values_list('subject_id', flat=True).distinct()

        subjects = Subject.objects.filter(tenant=tenant, is_active=True)
        if subject_ids.exists():
            subjects = subjects.filter(id__in=subject_ids)
        elif session.classroom.grade_level:
            subjects = subjects.filter(grade_levels__contains=[session.classroom.grade_level])

        subjects = subjects.order_by('order', 'name')
        subject_lookup = {subject.code.upper(): subject for subject in subjects}

        # Read CSV and normalize headers
        content = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        normalized_headers = {h.strip().upper(): h for h in reader.fieldnames or []}
        # Build a reverse mapping from normalized header to original
        header_map = {norm: orig for orig, norm in normalized_headers.items()}

        created = 0
        updated = 0
        errors = []

        with transaction.atomic():
            for i, raw_row in enumerate(reader, start=2):
                # Normalize row keys to uppercase for reliable access
                row = {k.strip().upper(): v.strip() for k, v in raw_row.items() if v is not None}

                admission_number = row.get('ADMISSION_NUMBER', '')
                index_number = row.get('INDEX_NUMBER', '')

                if not admission_number:
                    errors.append({'row': i, 'field': 'admission_number', 'message': 'Missing admission number'})
                    continue

                candidate = NationalExamCandidate.objects.filter(
                    tenant=tenant,
                    session=session,
                    student__admission_number=admission_number,
                ).select_related('student').first()
                if not candidate:
                    errors.append({'row': i, 'field': 'admission_number', 'message': f'Candidate {admission_number} not found in this session'})
                    continue

                # Update index number if provided
                if index_number and candidate.index_number != index_number:
                    candidate.index_number = index_number
                    candidate.save(update_fields=['index_number'])

                # Determine if the row uses the "subject_code" column format
                if 'SUBJECT_CODE' in row:
                    subject_code = row.get('SUBJECT_CODE', '').upper()
                    marks_str = row.get('MARKS', '')
                    total_marks_str = row.get('TOTAL_MARKS', '')
                    grade = row.get('GRADE', '').upper()
                    remarks = row.get('REMARKS', '')

                    if not subject_code:
                        errors.append({'row': i, 'field': 'subject_code', 'message': 'Missing subject code'})
                        continue

                    subject = subject_lookup.get(subject_code)
                    if not subject:
                        errors.append({'row': i, 'field': 'subject_code', 'message': f'Subject {subject_code} not allowed for this exam'})
                        continue

                    total_marks = 100
                    if total_marks_str:
                        try:
                            total_marks = int(total_marks_str)
                            if total_marks <= 0:
                                raise ValueError
                        except Exception:
                            errors.append({'row': i, 'field': 'total_marks', 'message': f'Invalid total marks "{total_marks_str}"'})
                            continue

                    marks = None
                    if marks_str:
                        try:
                            marks = Decimal(marks_str)
                            if marks < 0 or marks > total_marks:
                                errors.append({'row': i, 'field': 'marks', 'message': f'Marks {marks} out of range (0-{total_marks})'})
                                continue
                        except Exception:
                            errors.append({'row': i, 'field': 'marks', 'message': f'Invalid marks "{marks_str}"'})
                            continue
                    elif not grade:
                        errors.append({'row': i, 'field': 'marks', 'message': 'Either marks or grade must be provided'})
                        continue

                    if grade and grade not in ['EE','ME','AE','BE']:
                        errors.append({'row': i, 'field': 'grade', 'message': f'Invalid grade "{grade}"'})
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
                    continue  # row processed, move to next

                # Otherwise, process all subject columns present in the row
                for subject_code, subject in subject_lookup.items():
                    marks_str = row.get(subject_code, '')
                    if not marks_str:
                        continue  # skip empty cells
                    try:
                        marks = Decimal(marks_str)
                        if marks < 0 or marks > 100:  # national exam total is typically 100
                            errors.append({'row': i, 'field': subject_code, 'message': f'Marks {marks} out of range (0-100)'})
                            continue
                    except Exception:
                        errors.append({'row': i, 'field': subject_code, 'message': f'Invalid marks "{marks_str}"'})
                        continue

                    # For subject-column format, total_marks is fixed at 100 and grade is auto-computed
                    _, created_flag = NationalExamResult.objects.update_or_create(
                        tenant=tenant,
                        candidate=candidate,
                        subject=subject,
                        defaults={
                            'marks': marks,
                            'total_marks': 100,
                            'grade': '',  # auto-computed in save()
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
            'total_rows_processed': i - 1,  # Actual processed rows (excluding header)
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