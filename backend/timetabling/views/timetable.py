from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from students.models import Student

from ..models import TimetableEntry, TimetableJob
from ..permissions import IsTimetableAdmin, IsTimetableAdminOrReadOnly, is_admin, is_parent, is_teacher
from ..serializers import (
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
    permission_classes = [IsTimetableAdmin]

    def get(self, request):
        return Response(check_timetable_readiness(request.user.tenant))


class TimetableJobViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = TimetableJob.objects.select_related('created_by').order_by('-created_at')
    serializer_class = TimetableJobSerializer
    permission_classes = [IsTimetableAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['term', 'academic_year', 'status']
    # A school's job history is always small and bounded (one row per generate/
    # regenerate click), and the wizard/timetable page always wants the full
    # list to find the latest job — never worth paginating.
    pagination_class = None

    def create(self, request, *args, **kwargs):
        readiness = check_timetable_readiness(request.user.tenant)
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


class TimetableEntryViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = TimetableEntry.objects.select_related(
        'job', 'classroom', 'subject', 'teacher', 'period', 'period__schedule_template', 'room',
    )
    permission_classes = [IsTimetableAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['job', 'classroom', 'teacher', 'subject', 'period', 'locked']
    # A single job's entries are a bounded, known-size set — roughly
    # (active classrooms) x (non-break periods per week). The admin grid and
    # the read-only student/teacher/parent views all need the FULL set for a
    # job to render correctly; paginating this silently truncated a 706-entry
    # job down to the first page (20 rows), making a correctly-generated
    # whole-week timetable look like it only covered Monday.
    pagination_class = None

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return TimetableEntryUpdateSerializer
        return TimetableEntrySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not is_admin(user):
            qs = qs.filter(job__published=True)
        if is_teacher(user):
            qs = qs.filter(teacher=user)
        if is_parent(user):
            classroom_ids = Student.objects.filter(
                tenant=user.tenant,
                primary_guardian__user=user,
                is_active=True,
            ).values_list('classroom_id', flat=True)
            qs = qs.filter(classroom_id__in=classroom_ids)
        return qs

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