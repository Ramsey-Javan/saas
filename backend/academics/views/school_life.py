"""Attendance, timetable, co-curricular and report card viewsets."""
import io
import zipfile
from datetime import timedelta
import csv

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from students.models import Classroom, Student

from ..models import (
    AttendanceRecord,
    AttendanceSession,
    CBCGrade,
    ClassTimetable,
    CoCurricularActivity,
    ExamResult,
    ReportCard,
    StudentCoCurricular,
    TimetablePDF
)
from ..permissions import (
    CanViewReportCard,
    CanViewTimetable,
    IsAdminUser,
    IsTeacherOrAdmin,
    user_owns_student,
)
from ..serializers import (
    AttendanceSessionListSerializer,
    AttendanceSessionSerializer,
    ClassTimetableSerializer,
    CoCurricularActivitySerializer,
    GenerateReportCardSerializer,
    MarkAttendanceSerializer,
    ReportCardSerializer,
    StudentCoCurricularSerializer,
    TimetablePDFSerializer,
)
from .mixins import (
    TenantScopedMixin,
    _is_admin,
    _is_teacher,
    _is_parent,
    _teacher_classroom_ids,
    _teacher_subject_ids,
    _validate_student_for_user,
)


class AttendanceSessionViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = AttendanceSession.objects.select_related('classroom', 'subject', 'teacher').prefetch_related(
        'records__student'
    ).order_by('-date', 'classroom__name', 'session_type')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['classroom', 'date', 'session_type', 'term', 'academic_year', 'is_locked']

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_teacher(self.request.user):
            from students.models import Classroom

            homeroom_ids = set(
                Classroom.objects.filter(
                    tenant=self.request.user.tenant, class_teacher=self.request.user
                ).values_list('id', flat=True)
            )
            subject_ids = set(_teacher_classroom_ids(self.request.user))
            qs = qs.filter(classroom_id__in=homeroom_ids | subject_ids)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return AttendanceSessionListSerializer
        return AttendanceSessionSerializer

    def get_permissions(self):
        if self.action in ['lock', 'destroy']:
            return [IsAdminUser()]
        return [IsTeacherOrAdmin()]

    REGISTER_SESSION_TYPES = {'daily', 'morning', 'afternoon'}

    def _check_attendance_permission(self, classroom, session_type, subject=None):
        if not _is_teacher(self.request.user):
            return

        user = self.request.user
        is_homeroom = getattr(classroom, 'class_teacher_id', None) == user.id
        teaches_class = classroom.id in set(_teacher_classroom_ids(user))

        if session_type in self.REGISTER_SESSION_TYPES:
            if not is_homeroom and not teaches_class:
                raise PermissionDenied(
                    'Only assigned teachers can manage the daily register for this class.'
                )
            return

        if is_homeroom:
            return
        if not teaches_class:
            raise PermissionDenied(
                'You can only manage lesson attendance for classes you teach.'
            )
        if subject is not None and subject.id not in set(_teacher_subject_ids(user)):
            raise PermissionDenied(
                'You can only manage lesson attendance for your assigned subjects.'
            )

    def _check_date_constraints(self, date, instance=None):
        """Validate session dates: no future, no too-old, respect auto-lock."""
        today = timezone.localdate()

        # 1. No future dates
        if date > today:
            raise ValidationError('Cannot create attendance sessions for future dates.')

        # 2. No backdating beyond 7 days
        if date < today - timedelta(days=7):
            raise ValidationError('Cannot create attendance sessions older than 7 days.')

        # 3. Auto-lock grace period from tenant settings
        tenant = self.request.user.tenant
        auto_lock_days = getattr(tenant, 'attendance_auto_lock_days', 2)
        if instance and instance.is_locked:
            raise ValidationError('This session is locked and cannot be edited.')
        if instance and (today - instance.date).days > auto_lock_days:
            raise ValidationError(
                f'This session can no longer be edited (past {auto_lock_days}-day grace period).'
            )

    def _check_duplicate_session(self, classroom, date, session_type, subject, exclude_id=None):
        """Prevent duplicate sessions for same class/date/type/subject."""
        qs = AttendanceSession.objects.filter(
            tenant=self.request.user.tenant,
            classroom=classroom,
            date=date,
            session_type=session_type,
            subject=subject,
        )
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        if qs.exists():
            subject_label = f' ({subject.name})' if subject else ''
            raise ValidationError(
                f'A {session_type} session already exists for {classroom}{subject_label} on {date}.'
            )

    def _auto_populate_records(self, session):
        """Create present records for all active students in the class."""
        students = Student.objects.filter(
            tenant=session.tenant,
            classroom=session.classroom,
            is_active=True,
        )
        existing_student_ids = set(
            session.records.values_list('student_id', flat=True)
        )
        new_students = students.exclude(id__in=existing_student_ids)
        if new_students.exists():
            AttendanceRecord.objects.bulk_create([
                AttendanceRecord(
                    tenant=session.tenant,
                    session=session,
                    student=s,
                    status='P',
                )
                for s in new_students
            ])

    def perform_create(self, serializer):
        classroom = serializer.validated_data['classroom']
        subject = serializer.validated_data.get('subject')
        session_type = serializer.validated_data.get('session_type', AttendanceSession.SessionType.DAILY)
        date = serializer.validated_data.get('date')

        if classroom.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom must belong to your school.')
        if subject and subject.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Subject must belong to your school.')

        self._check_attendance_permission(classroom, session_type, subject)
        self._check_date_constraints(date)
        self._check_duplicate_session(classroom, date, session_type, subject)

        serializer.save(tenant=self.request.user.tenant, teacher=self.request.user)
        self._auto_populate_records(serializer.instance)

    def perform_update(self, serializer):
        classroom = serializer.validated_data.get('classroom', serializer.instance.classroom)
        subject = serializer.validated_data.get('subject', serializer.instance.subject)
        session_type = serializer.validated_data.get('session_type', serializer.instance.session_type)
        date = serializer.validated_data.get('date', serializer.instance.date)

        if classroom.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Classroom must belong to your school.')
        if subject and subject.tenant_id != self.request.user.tenant_id:
            raise ValidationError('Subject must belong to your school.')

        self._check_attendance_permission(classroom, session_type, subject)
        self._check_date_constraints(date, instance=serializer.instance)
        self._check_duplicate_session(classroom, date, session_type, subject, exclude_id=serializer.instance.id)

        serializer.save(tenant=self.request.user.tenant)

    @action(detail=True, methods=['post'], url_path='mark')
    def mark(self, request, pk=None):
        session = self.get_object()
        if session.is_locked:
            return Response(
                {'error': 'Session is locked and cannot be edited.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        self._check_attendance_permission(session.classroom, session.session_type, session.subject)
        self._check_date_constraints(session.date, instance=session)

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
    
    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser], url_path='unlock')
    def unlock(self, request, pk=None):
        session = self.get_object()
        session.is_locked = False
        session.save(update_fields=['is_locked'])
        return Response({'detail': 'Session unlocked.'})

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
    
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """
        GET /api/academics/sessions/export/?classroom=1&date_after=2026-01-01&date_before=2026-12-31
        Exports attendance sessions as CSV — one file per classroom, bundled in a ZIP.
        """
        from django.http import HttpResponse
        import zipfile
        import io
        import csv

        qs = self.get_queryset().filter(is_locked=True)
        
        classroom_id = request.query_params.get('classroom')
        date_after = request.query_params.get('date_after')
        date_before = request.query_params.get('date_before')
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')

        if classroom_id:
            qs = qs.filter(classroom_id=classroom_id)
        if date_after:
            qs = qs.filter(date__gte=date_after)
        if date_before:
            qs = qs.filter(date__lte=date_before)
        if term:
            qs = qs.filter(term=term)
        if academic_year:
            qs = qs.filter(academic_year=int(academic_year))

        # Group sessions by classroom
        from collections import defaultdict
        by_classroom = defaultdict(list)
        for session in qs.prefetch_related('records__student'):
            by_classroom[str(session.classroom)].append(session)

        if not by_classroom:
            return Response({'error': 'No locked sessions found for export.'}, status=status.HTTP_404_NOT_FOUND)

        # Create ZIP with one CSV per classroom
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for classroom_name, sessions in by_classroom.items():
                csv_buffer = io.StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow([
                    'Session ID', 'Classroom', 'Date', 'Session Type', 'Term', 'Academic Year',
                    'Student Name', 'Admission Number', 'Status', 'Remarks', 'Locked'
                ])

                for session in sessions:
                    for record in session.records.all():
                        writer.writerow([
                            session.id,
                            str(session.classroom),
                            session.date,
                            session.session_type,
                            session.term,
                            session.academic_year,
                            record.student.get_full_name(),
                            record.student.admission_number,
                            record.status,
                            record.remarks or '',
                            'Yes',
                        ])

                # Sanitize filename: replace spaces/slashes
                safe_name = classroom_name.replace(' ', '_').replace('/', '_')
                filename = f'attendance_{safe_name}.csv'
                zf.writestr(filename, csv_buffer.getvalue())

        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="attendance_export_{timezone.localdate()}.zip"'
        return response
        

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
class TimetablePDFViewSet(viewsets.ModelViewSet):
    queryset = TimetablePDF.objects.select_related('classroom').order_by('-created_at')
    serializer_class = TimetablePDFSerializer
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['classroom', 'term', 'academic_year']

    def get_queryset(self):
        qs = TimetablePDF.objects.select_related('classroom').order_by('-created_at')
        tenant = getattr(self.request.user, 'tenant', None)
        if tenant:
            return qs.filter(tenant=tenant)
        return qs.none()

    def perform_create(self, serializer):
        tenant = getattr(self.request.user, 'tenant', None)
        serializer.save(tenant=tenant, uploaded_by=self.request.user)

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

    def _pdf_common_data(self, report_card, request):
        """Gather common data used by both full and exam-only PDFs."""
        tenant = request.user.tenant
        student = report_card.student
        classroom = report_card.classroom

        if _is_parent(request.user):
            if not user_owns_student(request.user, report_card.student):
                return None, Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
            if report_card.status != 'published':
                return None, Response({'error': 'Report card not yet published.'}, status=status.HTTP_403_FORBIDDEN)

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

        return {
            'tenant': tenant,
            'student': student,
            'classroom': classroom,
            'report_card': report_card,
            'grades': grades,
            'co_curricular': co_curricular,
            'exam_results': exam_results,
        }, None

    def _build_pdf_response(self, report_card, data, include_grades=True):
        """Build the actual PDF and return an HttpResponse."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader, simpleSplit
        from reportlab.pdfgen import canvas

        tenant = data['tenant']
        student = data['student']
        classroom = data['classroom']
        report_card = data['report_card']
        grades = data['grades']
        co_curricular = data['co_curricular']
        exam_results = data['exam_results']

        response = HttpResponse(content_type='application/pdf')
        filename = f'{student.admission_number}.pdf'
        response['Content-Disposition'] = f'inline; filename="{filename}"'

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

        # ── CBC GRADES SECTION (only for full PDF) ──
        if include_grades:
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

        # ── EXAM RESULTS SECTION ──
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

        # ── ATTENDANCE SECTION ──
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

        # ── CO-CURRICULAR SECTION ──
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

        # ── CONDUCT SECTION ──
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

        # ── REMARKS SECTION ──
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

        # ── DATES & SIGNATURES ──
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

    @action(detail=True, methods=['get'], permission_classes=[CanViewReportCard], url_path='pdf')
    def pdf(self, request, pk=None):
        report_card = self.get_object()
        data, error = self._pdf_common_data(report_card, request)
        if error:
            return error
        return self._build_pdf_response(report_card, data, include_grades=True)

    @action(detail=True, methods=['get'], permission_classes=[CanViewReportCard], url_path='exam-pdf')
    def exam_pdf(self, request, pk=None):
        report_card = self.get_object()
        data, error = self._pdf_common_data(report_card, request)
        if error:
            return error
        return self._build_pdf_response(report_card, data, include_grades=False)

    @action(detail=False, methods=['post'], permission_classes=[CanViewReportCard], url_path='bulk-pdf')
    def bulk_pdf(self, request):
        """
        POST /api/academics/report-cards/bulk-pdf/
        Body: { ids: [1, 2, 3], exam_only: false }
        Returns a ZIP file containing all selected PDFs.
        """
        ids = request.data.get('ids', [])
        exam_only = request.data.get('exam_only', False)

        if not ids:
            return Response({'error': 'ids required'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = request.user.tenant
        report_cards = ReportCard.objects.filter(
            id__in=ids,
            tenant=tenant,
        ).select_related('student', 'classroom')

        # Permission check
        if _is_teacher(request.user):
            report_cards = report_cards.filter(classroom_id__in=_teacher_classroom_ids(request.user))
        if _is_parent(request.user):
            report_cards = report_cards.filter(
                student__primary_guardian__user=request.user,
                status='published'
            )

        if not report_cards.exists():
            return Response({'error': 'No report cards found.'}, status=status.HTTP_404_NOT_FOUND)

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for report_card in report_cards:
                data, error = self._pdf_common_data(report_card, request)
                if error:
                    continue
                pdf_response = self._build_pdf_response(report_card, data, include_grades=not exam_only)
                pdf_content = pdf_response.content
                filename = f'{report_card.student.admission_number}.pdf'
                zip_file.writestr(filename, pdf_content)

        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="report_cards.zip"'
        return response

    @action(detail=False, methods=['get'], url_path='student/(?P<student_id>[^/.]+)')
    def student_report_cards(self, request, student_id=None):
        _validate_student_for_user(request.user, student_id)
        qs = self.get_queryset().filter(student_id=student_id).order_by('-academic_year', '-term')
        if _is_parent(request.user):
            qs = qs.filter(status='published')
        return Response(ReportCardSerializer(qs, many=True, context={'request': request}).data)