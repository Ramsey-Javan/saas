from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from accounts.models import CustomUser
from students.models import Classroom, Student

from ..models import TeacherSubjectAssignment, TimetableEntry, TimetableJob
from ..permissions import IsTimetableAdmin, IsTimetableAdminOrReadOnly, is_admin, is_parent, is_teacher
from ..serializers import (
    CopyTimetableSerializer,
    PartialRegenerateSerializer,
    TimetableEntrySerializer,
    TimetableEntryUpdateSerializer,
    TimetableJobSerializer,
)
from ..services.readiness import check_timetable_readiness
from ..services.validation import TimetableMove, validate_timetable_move
from ..tasks import generate_timetable_task, regenerate_partial_task
from .mixins import TenantScopedMixin


class ReadinessView(APIView):
    permission_classes = [IsTimetableAdminOrReadOnly]

    def get(self, request):
        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')
        if not term or not academic_year:
            return Response(
                {'detail': 'term and academic_year query params are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            academic_year = int(academic_year)
        except ValueError:
            return Response(
                {'detail': 'academic_year must be an integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(check_timetable_readiness(request.user.tenant, term, academic_year))


class TimetableJobViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = TimetableJob.objects.select_related('created_by').order_by('-created_at')
    serializer_class = TimetableJobSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['term', 'academic_year', 'status']
    pagination_class = None

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsTimetableAdminOrReadOnly()]
        return [IsTimetableAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        if not is_admin(self.request.user):
            qs = qs.filter(published=True)
        return qs

    def create(self, request, *args, **kwargs):
        term = request.data.get('term')
        academic_year = request.data.get('academic_year')
        if not term or not academic_year:
            return Response(
                {'detail': 'term and academic_year are required to generate a timetable.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        readiness = check_timetable_readiness(request.user.tenant, term, academic_year)
        if not readiness['ready']:
            return Response(readiness, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.save(tenant=request.user.tenant, created_by=request.user)
        generate_timetable_task.apply_async(args=[job.id, request.user.tenant_id], queue='timetable_solver')
        return Response(self.get_serializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='regenerate-partial')
    def regenerate_partial(self, request, pk=None):
        job = self.get_object()
        serializer = PartialRegenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job.status = TimetableJob.Status.PENDING
        job.failure_reason = ''
        job.save(update_fields=['status', 'failure_reason', 'updated_at'])
        regenerate_partial_task.apply_async(
            args=[job.id, request.user.tenant_id, serializer.validated_data['class_stream_ids']],
            queue='timetable_solver',
        )
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=['post'], url_path='publish')
    def publish(self, request, pk=None):
        job = self.get_object()
        job.published = True
        job.published_at = timezone.now()
        job.save(update_fields=['published', 'published_at', 'updated_at'])
        return Response(self.get_serializer(job).data)

    @action(detail=False, methods=['post'], url_path='copy-from-term')
    def copy_from_term(self, request):
        serializer = CopyTimetableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = request.user.tenant

        source_term = serializer.validated_data['source_term']
        source_year = serializer.validated_data['source_academic_year']
        target_term = serializer.validated_data['target_term']
        target_year = serializer.validated_data['target_academic_year']

        source_job = TimetableJob.objects.filter(
            tenant=tenant,
            term=source_term,
            academic_year=source_year,
            status=TimetableJob.Status.DONE,
        ).order_by('-published', '-created_at').first()

        if not source_job:
            return Response(
                {'detail': f'No completed timetable found for {source_term} {source_year}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            target_job = TimetableJob.objects.create(
                tenant=tenant,
                term=target_term,
                academic_year=target_year,
                status=TimetableJob.Status.DONE,
                created_by=request.user,
                published=False,
            )

            entries_to_create = []
            for entry in source_job.entries.select_related('classroom', 'subject', 'teacher', 'period', 'room'):
                entries_to_create.append(TimetableEntry(
                    tenant=tenant,
                    job=target_job,
                    classroom=entry.classroom,
                    subject=entry.subject,
                    teacher=entry.teacher,
                    period=entry.period,
                    room=entry.room,
                    locked=entry.locked,
                ))

            if entries_to_create:
                TimetableEntry.objects.bulk_create(entries_to_create, batch_size=500)

            source_assignments = TeacherSubjectAssignment.objects.filter(
                tenant=tenant,
                term=source_term,
                academic_year=source_year,
            )
            created_count = 0
            for a in source_assignments:
                _, was_created = TeacherSubjectAssignment.objects.get_or_create(
                    tenant=tenant,
                    teacher=a.teacher,
                    subject=a.subject,
                    classroom=a.classroom,
                    term=target_term,
                    academic_year=target_year,
                )
                if was_created:
                    created_count += 1

        return Response({
            'job': TimetableJobSerializer(target_job, context={'request': request}).data,
            'entries_copied': len(entries_to_create),
            'assignments_created': created_count,
        })


class TimetableEntryFilter(django_filters.FilterSet):
    teacher = django_filters.CharFilter(method='filter_teacher')

    class Meta:
        model = TimetableEntry
        fields = ['job', 'classroom', 'subject', 'period', 'locked']

    def filter_teacher(self, queryset, name, value):
        """
        Accepts either a numeric user PK or an employee ID string
        (e.g. EMP/2026/0001).
        """
        q = Q()

        for field in ('employee_id', 'staff_id', 'username', 'email'):
            if hasattr(CustomUser, field):
                q |= Q(**{field: value})

        try:
            from accounts.models import StaffProfile
            sp_q = Q()
            for field in ('employee_id', 'staff_id'):
                if hasattr(StaffProfile, field):
                    sp_q |= Q(**{field: value})
            if value.isdigit():
                sp_q |= Q(user_id=int(value))
            if sp_q.children:
                staff_user_ids = StaffProfile.objects.filter(sp_q).values_list('user_id', flat=True)
                q |= Q(pk__in=staff_user_ids)
        except ImportError:
            pass

        if value.isdigit():
            q |= Q(pk=int(value))

        user_ids = CustomUser.objects.filter(q).values_list('id', flat=True)
        return queryset.filter(teacher_id__in=user_ids)


class TimetableEntryViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = TimetableEntry.objects.select_related(
        'job', 'classroom', 'subject', 'teacher', 'period', 'period__schedule_template', 'room',
    )
    permission_classes = [IsTimetableAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = TimetableEntryFilter
    pagination_class = None

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return TimetableEntryUpdateSerializer
        return TimetableEntrySerializer

    # ── NEW: helper to check class-teacher rights ──
    def _is_class_teacher(self, user, classroom):
        for field in ('class_teacher', 'stream_teacher', 'form_teacher'):
            if hasattr(classroom, field) and getattr(classroom, field) == user:
                return True
        return False

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        classroom_id = self.request.query_params.get('classroom')

        # Non-admins only see published timetables
        if not is_admin(user):
            qs = qs.filter(job__published=True)

        if is_teacher(user):
            if classroom_id:
                # ── CLASS-TEACHER MODE ──
                # Teacher asked for a specific class.
                # Allow it ONLY if they are the class teacher.
                try:
                    classroom = Classroom.objects.get(
                        id=classroom_id,
                        tenant=user.tenant,
                    )
                except Classroom.DoesNotExist:
                    # Class doesn't exist → empty result
                    return qs.none()

                if self._is_class_teacher(user, classroom):
                    # Return the full timetable for this class
                    qs = qs.filter(classroom=classroom)
                else:
                    # Not their class → fall back to their own periods only
                    qs = qs.filter(teacher=user)
            else:
                # ── DEFAULT: MY TEACHING SCHEDULE ──
                qs = qs.filter(teacher=user)

        if is_parent(user):
            classroom_ids = Student.objects.filter(
                tenant=user.tenant,
                primary_guardian__user=user,
                is_active=True,
            ).values_list('classroom_id', flat=True)
            qs = qs.filter(classroom_id__in=classroom_ids)

        return qs

    @action(detail=False, methods=['get'], url_path='my-classes')
    def my_classes(self, request):
        """
        Returns the list of classrooms where the current teacher
        is a class teacher (for the frontend dropdown).
        """
        user = request.user
        if not is_teacher(user):
            return Response([])

        q = Q()
        for field in ('class_teacher', 'stream_teacher', 'form_teacher'):
            if hasattr(Classroom, field):
                q |= Q(**{field: user})

        if not q.children:
            return Response([])

        classrooms = Classroom.objects.filter(q, tenant=user.tenant).order_by('grade_level', 'name', 'stream')
        data = [{'id': c.id, 'name': str(c)} for c in classrooms]
        return Response(data)

    def perform_update(self, serializer):
        if not is_admin(self.request.user):
            raise PermissionDenied('Only admins can edit timetable entries.')
        instance = serializer.instance
        data = {**{field: getattr(instance, field) for field in ['classroom', 'subject', 'teacher', 'period', 'room']}, **serializer.validated_data}
        validate_timetable_move(TimetableMove(
            tenant=self.request.user.tenant,
            job=instance.job,
            classroom=data['classroom'],
            subject=data['subject'],
            teacher=data['teacher'],
            period=data['period'],
            room=data.get('room'),
            entry_id=instance.id,
        ))
        serializer.save(tenant=self.request.user.tenant, locked=True)

    def perform_create(self, serializer):
        if not is_admin(self.request.user):
            raise PermissionDenied('Only admins can create timetable entries.')
        data = serializer.validated_data
        validate_timetable_move(TimetableMove(
            tenant=self.request.user.tenant,
            job=data['job'],
            classroom=data['classroom'],
            subject=data['subject'],
            teacher=data['teacher'],
            period=data['period'],
            room=data.get('room'),
        ))
        serializer.save(tenant=self.request.user.tenant, locked=True)

    @action(detail=True, methods=['post'], url_path='lock')
    def lock(self, request, pk=None):
        if not is_admin(request.user):
            raise PermissionDenied('Only admins can lock timetable entries.')
        entry = self.get_object()
        locked = bool(request.data.get('locked', not entry.locked))
        with transaction.atomic():
            entry.locked = locked
            entry.save(update_fields=['locked', 'updated_at'])
        return Response(TimetableEntrySerializer(entry, context={'request': request}).data)


class TimetablePDFDownloadView(APIView):
    permission_classes = [IsTimetableAdminOrReadOnly]

    def get(self, request):
        from ..models import Period

        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')
        classroom_id = request.query_params.get('classroom')
        teacher_id = request.query_params.get('teacher')

        if not term or not academic_year:
            return Response({'detail': 'term and academic_year are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            academic_year = int(academic_year)
        except ValueError:
            return Response({'detail': 'academic_year must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = request.user.tenant

        if is_teacher(request.user):
            if teacher_id:
                try:
                    if int(teacher_id) != request.user.id:
                        raise PermissionDenied('You can only download your own timetable.')
                except ValueError:
                    raise PermissionDenied('Invalid teacher_id.')
            else:
                teacher_id = str(request.user.id)

        if is_parent(request.user):
            raise PermissionDenied('PDF download not available for parents.')

        job = TimetableJob.objects.filter(
            tenant=tenant,
            term=term,
            academic_year=academic_year,
            status=TimetableJob.Status.DONE,
        ).order_by('-created_at').first()

        if not job:
            return Response({'detail': 'No generated timetable found for this term.'}, status=status.HTTP_404_NOT_FOUND)

        if not is_admin(request.user) and not job.published:
            raise PermissionDenied('Timetable not yet published.')

        entries = TimetableEntry.objects.filter(tenant=tenant, job=job)
        if classroom_id:
            entries = entries.filter(classroom_id=classroom_id)
        if teacher_id:
            entries = entries.filter(teacher_id=teacher_id)

        if not entries.exists():
            return Response({'detail': 'No entries found.'}, status=status.HTTP_404_NOT_FOUND)

        if classroom_id:
            classrooms_to_render = [entries.first().classroom]
        else:
            classrooms_to_render = list(
                Classroom.objects.filter(
                    id__in=entries.values_list('classroom_id', flat=True).distinct()
                ).order_by('grade_level', 'name', 'stream')
            )

        response = HttpResponse(content_type='application/pdf')
        filename = f'timetable_{term}_{academic_year}'
        if classroom_id:
            filename += f'_{classrooms_to_render[0].name or classrooms_to_render[0].id}'
        if teacher_id:
            teacher = entries.first().teacher
            filename += f'_{teacher.get_full_name() or teacher.id}'
        filename = filename.replace(' ', '_') + '.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        doc = SimpleDocTemplate(
            response,
            pagesize=landscape(A4),
            rightMargin=1 * cm,
            leftMargin=1 * cm,
            topMargin=1 * cm,
            bottomMargin=1 * cm,
        )

        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'TimetableTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1,
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            'TimetableSubtitle',
            parent=styles['Normal'],
            fontSize=10,
            alignment=1,
            spaceAfter=12,
            textColor=colors.grey,
        )
        cell_style = ParagraphStyle(
            'TimetableCell',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            alignment=1,
        )
        day_style = ParagraphStyle(
            'TimetableDay',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            alignment=1,
        )
        period_header_style = ParagraphStyle(
            'PeriodHeader',
            parent=styles['Normal'],
            fontSize=9,
            leading=10,
            alignment=1,
        )

        days = [(1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'), (4, 'Thursday'), (5, 'Friday')]
        page_width, _ = landscape(A4)
        available_width = page_width - 2 * cm  # 1cm left + 1cm right margin

        for idx, classroom in enumerate(classrooms_to_render):
            if idx > 0:
                elements.append(PageBreak())

            cls_entries = entries.filter(classroom=classroom)

            school_name = tenant.name or 'School'
            elements.append(Paragraph(f'<b>{school_name}</b>', title_style))
            elements.append(Paragraph(f'Timetable — {term} {academic_year}', subtitle_style))

            header_text = f'<b>Class:</b> {classroom}'
            if teacher_id:
                teacher = cls_entries.first().teacher if cls_entries.exists() else None
                if teacher:
                    header_text += f' &nbsp;&nbsp; <b>Teacher:</b> {teacher.get_full_name() or teacher.email}'
            elements.append(Paragraph(header_text, subtitle_style))
            elements.append(Spacer(1, 0.2 * cm))

            # Fetch periods with start/end times per classroom
            schedule_templates = cls_entries.values_list('period__schedule_template', flat=True).distinct()
            periods_qs = Period.objects.filter(
                tenant=tenant,
                schedule_template__in=schedule_templates,
                is_break=False,
            ).order_by('order')

            # Deduplicate by order (safety net if multiple templates share an order)
            seen_orders = set()
            periods = []
            for p in periods_qs:
                if p.order not in seen_orders:
                    seen_orders.add(p.order)
                    periods.append(p)

            period_orders = [p.order for p in periods]
            if not period_orders:
                period_orders = sorted(set(cls_entries.values_list('period__order', flat=True)))

            # Dynamic column widths so table never overflows page
            day_col_width = 2.2 * cm
            period_col_width = (available_width - day_col_width) / max(len(period_orders), 1)
            col_widths = [day_col_width] + [period_col_width] * len(period_orders)

            # Shrink font slightly when there are many periods
            if len(period_orders) > 8:
                cell_style.fontSize = 7
                cell_style.leading = 9

            # Header now shows P# + time range
            header = [Paragraph('<b>Day</b>', day_style)]
            for period in periods:
                start = getattr(period, 'start_time', None) or getattr(period, 'start', None)
                end = getattr(period, 'end_time', None) or getattr(period, 'end', None)
                time_str = ""
                if start and end:
                    time_str = f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
                header.append(Paragraph(
                    f'<b>P{period.order}</b><br/><span fontSize="7" textColor="#6b7280">{time_str}</span>',
                    period_header_style
                ))
            if not periods:
                for o in period_orders:
                    header.append(Paragraph(f'<b>P{o}</b>', period_header_style))

            table_data = [header]

            for day_num, day_name in days:
                row = [Paragraph(f'<b>{day_name}</b>', day_style)]
                for order in period_orders:
                    cell_entries = cls_entries.filter(period__day_of_week=day_num, period__order=order)
                    if cell_entries.exists():
                        cell_texts = []
                        for e in cell_entries:
                            parts = [f'<b>{e.subject.name}</b>']
                            if not teacher_id:
                                parts.append(f'{e.teacher.get_full_name() or e.teacher.email}')
                            if e.room:
                                parts.append(f'Rm: {e.room.name}')
                            cell_texts.append('<br/>'.join(parts))
                        row.append(Paragraph('<br/><br/>'.join(cell_texts), cell_style))
                    else:
                        row.append(Paragraph('—', cell_style))
                table_data.append(row)

            table = Table(table_data, colWidths=col_widths, repeatRows=1)

            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#374151')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))

            elements.append(table)

        doc.build(elements)
        return response