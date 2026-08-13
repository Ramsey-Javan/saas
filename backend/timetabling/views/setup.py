import django_filters
from django.db import IntegrityError, transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from academics.models import Subject
from accounts.models import CustomUser
from students.models import Classroom

from ..models import (
    Period,
    RoomResource,
    ScheduleTemplate,
    SubjectRule,
    TeacherAvailability,
    TeacherWorkloadLimit,
)
from ..models import TeacherSubjectAssignment
from ..permissions import IsTimetableAdmin
from ..serializers import (
    BulkTeacherSubjectAssignmentSerializer,
    PeriodSerializer,
    RoomResourceSerializer,
    ScheduleTemplateSerializer,
    SubjectRuleSerializer,
    TeacherAvailabilitySerializer,
    TeacherSubjectAssignmentSerializer,
    TeacherWorkloadLimitSerializer,
)
from .mixins import TenantScopedMixin


class TeacherSubjectAssignmentFilter(django_filters.FilterSet):
    term = django_filters.CharFilter(field_name='term', lookup_expr='exact')
    academic_year = django_filters.NumberFilter(field_name='academic_year', lookup_expr='exact')

    class Meta:
        model = TeacherSubjectAssignment
        fields = ['teacher', 'subject', 'classroom', 'term', 'academic_year']


class AdminSetupViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsTimetableAdmin]
    # Every timetabling setup endpoint (schedule templates, periods, rooms,
    # subject rules, teacher availability/workload/assignments) is a small,
    # bounded per-school configuration list that the setup wizard always
    # fetches in full and holds in memory. Pagination on any of these silently
    # truncates that fetch to DRF's default page size — which caused rules and
    # assignments that genuinely existed to look "missing" to the frontend,
    # triggering duplicate-create attempts and assignments that appeared to
    # vanish. None of these lists are ever large enough to need pagination.
    pagination_class = None

    def _validate_related_tenant(self, serializer):
        tenant = self.request.user.tenant
        for value in serializer.validated_data.values():
            if hasattr(value, 'tenant_id') and value.tenant_id != tenant.id:
                raise serializers.ValidationError('Related records must belong to your school.')

    def perform_create(self, serializer):
        self._validate_related_tenant(serializer)
        try:
            with transaction.atomic():
                super().perform_create(serializer)
        except IntegrityError:
            raise serializers.ValidationError({
                'detail': (
                    'A record with these exact values already exists. '
                    'Refresh and edit the existing one instead of creating a new one.'
                ),
            })

    def perform_update(self, serializer):
        self._validate_related_tenant(serializer)
        try:
            with transaction.atomic():
                serializer.save(tenant=self.request.user.tenant)
        except IntegrityError:
            raise serializers.ValidationError({
                'detail': 'Saving this change would duplicate another existing record.',
            })


class ScheduleTemplateViewSet(AdminSetupViewSet):
    queryset = ScheduleTemplate.objects.order_by('name')
    serializer_class = ScheduleTemplateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']


class PeriodViewSet(AdminSetupViewSet):
    queryset = Period.objects.select_related('schedule_template').order_by('day_of_week', 'order')
    serializer_class = PeriodSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['schedule_template', 'day_of_week', 'is_break']
    # pagination_class = None is inherited from AdminSetupViewSet.

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if request.query_params.get('schedule_template'):
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['post'], url_path='bulk-update')
    def bulk_update(self, request):
        tenant = request.user.tenant
        schedule_template_id = request.data.get('schedule_template')
        periods_data = request.data.get('periods', [])

        if not schedule_template_id:
            return Response(
                {'detail': 'schedule_template is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(periods_data, list):
            return Response(
                {'detail': 'periods must be a list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template = ScheduleTemplate.objects.get(id=schedule_template_id, tenant=tenant)
        except ScheduleTemplate.DoesNotExist:
            return Response(
                {'detail': 'Schedule template not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Guard against duplicate (day, order) in the same request
        seen_keys = set()
        for item in periods_data:
            key = (item.get('day_of_week'), item.get('order'))
            if key in seen_keys:
                return Response(
                    {'detail': f'Duplicate period in request: day {key[0]} order {key[1]}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            seen_keys.add(key)

        with transaction.atomic():
            existing_qs = Period.objects.filter(tenant=tenant, schedule_template=template)
            existing_by_id = {p.id: p for p in existing_qs}
            existing_by_day_order = {}
            for p in existing_qs:
                existing_by_day_order[(p.day_of_week, p.order)] = p

            # Fixed snapshot of what existed BEFORE this request touches anything.
            # The cleanup delete below must only ever consider these IDs — never
            # a fresh re-query — or it will also catch (and immediately delete)
            # periods this same request just created via Period.objects.create().
            existing_ids_before = set(existing_by_id.keys())

            used_existing_ids = set()

            for item in periods_data:
                item_id = item.get('id')
                day = item.get('day_of_week')
                order = item.get('order')

                # Match by ID first, then by (day, order)
                period = None
                if item_id and item_id in existing_by_id:
                    period = existing_by_id[item_id]
                    if period.tenant_id != tenant.id or period.schedule_template_id != template.id:
                        period = None

                if not period:
                    period = existing_by_day_order.get((day, order))

                if period and period.id not in used_existing_ids:
                    period.day_of_week = day
                    period.order = order
                    period.start_time = item.get('start_time', period.start_time)
                    period.end_time = item.get('end_time', period.end_time)
                    period.is_break = item.get('is_break', period.is_break)
                    period.save()
                    used_existing_ids.add(period.id)
                else:
                    Period.objects.create(
                        tenant=tenant,
                        schedule_template=template,
                        day_of_week=day,
                        order=order,
                        start_time=item.get('start_time'),
                        end_time=item.get('end_time'),
                        is_break=item.get('is_break', False),
                    )

            # Only delete periods that existed before this request and were not
            # reused/matched by it. Restricting to existing_ids_before means this
            # can never touch rows created moments ago by the loop above, even
            # though a fresh query against the table would now include them.
            Period.objects.filter(
                tenant=tenant,
                schedule_template=template,
                id__in=existing_ids_before,
            ).exclude(id__in=used_existing_ids).delete()

        fresh = Period.objects.filter(
            tenant=tenant, schedule_template=template
        ).order_by('day_of_week', 'order')
        serializer = self.get_serializer(fresh, many=True)
        return Response(serializer.data)


class RoomResourceViewSet(AdminSetupViewSet):
    queryset = RoomResource.objects.order_by('room_type', 'name')
    serializer_class = RoomResourceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['room_type', 'is_active']


class SubjectRuleViewSet(AdminSetupViewSet):
    queryset = SubjectRule.objects.select_related('subject').prefetch_related('excluded_periods')
    serializer_class = SubjectRuleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['subject', 'grade_band', 'stream', 'requires_room_type', 'time_preference', 'is_active']

    @action(detail=False, methods=['post'], url_path='bulk-upsert')
    def bulk_upsert(self, request):
        tenant = request.user.tenant
        rules_data = request.data if isinstance(request.data, list) else request.data.get('rules', [])
        if not rules_data:
            return Response({'detail': 'No rules provided.'}, status=status.HTTP_400_BAD_REQUEST)

        valid_time_preferences = {choice for choice, _ in SubjectRule.TimePreference.choices}

        created_count = 0
        updated_count = 0
        errors = []

        with transaction.atomic():
            for idx, item in enumerate(rules_data):
                subject_id = item.get('subject')
                grade_band = item.get('grade_band')
                # Optional: blank/omitted stream means "applies to every stream in this grade",
                # matching Classroom.stream's own blank-string convention.
                stream = item.get('stream') or ''
                if not subject_id or not grade_band:
                    errors.append({'index': idx, 'detail': 'subject and grade_band are required.'})
                    continue

                if not Subject.objects.filter(id=subject_id, tenant=tenant).exists():
                    errors.append({'index': idx, 'detail': f'Subject {subject_id} not found.'})
                    continue

                time_preference = item.get('time_preference') or SubjectRule.TimePreference.NONE
                if time_preference not in valid_time_preferences:
                    time_preference = SubjectRule.TimePreference.NONE

                defaults = {
                    'periods_per_week': item.get('periods_per_week', 0),
                    'requires_double': item.get('requires_double', False),
                    'requires_room_type': item.get('requires_room_type') or None,
                    'is_hard_excluded': item.get('is_hard_excluded', True),
                    'time_preference': time_preference,
                    'is_active': item.get('is_active', True),
                }
                excluded_periods = item.get('excluded_periods', [])

                rule, was_created = SubjectRule.objects.update_or_create(
                    tenant=tenant,
                    subject_id=subject_id,
                    grade_band=grade_band,
                    stream=stream,
                    defaults=defaults,
                )
                if excluded_periods:
                    rule.excluded_periods.set(excluded_periods)
                else:
                    rule.excluded_periods.clear()

                if was_created:
                    created_count += 1
                else:
                    updated_count += 1

        return Response({
            'created': created_count,
            'updated': updated_count,
            'errors': errors,
        })

class TeacherAvailabilityViewSet(AdminSetupViewSet):
    queryset = TeacherAvailability.objects.select_related('teacher', 'period', 'period__schedule_template')
    serializer_class = TeacherAvailabilitySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['teacher', 'period', 'is_available']


class TeacherWorkloadLimitViewSet(AdminSetupViewSet):
    queryset = TeacherWorkloadLimit.objects.select_related('teacher')
    serializer_class = TeacherWorkloadLimitSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['teacher']


class TeacherSubjectAssignmentViewSet(AdminSetupViewSet):
    queryset = TeacherSubjectAssignment.objects.select_related('teacher', 'subject', 'classroom')
    serializer_class = TeacherSubjectAssignmentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = TeacherSubjectAssignmentFilter

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk(self, request):
        serializer = BulkTeacherSubjectAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = request.user.tenant
        teacher_id = serializer.validated_data['teacher']
        subject_id = serializer.validated_data['subject']
        classroom_ids = serializer.validated_data['classrooms']
        term = serializer.validated_data['term']
        academic_year = serializer.validated_data['academic_year']

        if not Subject.objects.filter(id=subject_id, tenant=tenant).exists():
            return Response({'subject': 'Subject not found in this school.'}, status=status.HTTP_400_BAD_REQUEST)
        if not CustomUser.objects.filter(id=teacher_id, tenant=tenant, role='teacher').exists():
            return Response({'teacher': 'Teacher not found in this school.'}, status=status.HTTP_400_BAD_REQUEST)

        classrooms = Classroom.objects.filter(id__in=classroom_ids, tenant=tenant)
        if classrooms.count() != len(set(classroom_ids)):
            return Response({'classrooms': 'One or more classes were not found in this school.'}, status=status.HTTP_400_BAD_REQUEST)

        created = 0
        with transaction.atomic():
            for classroom in classrooms:
                _, was_created = TeacherSubjectAssignment.objects.get_or_create(
                    tenant=tenant,
                    teacher_id=teacher_id,
                    subject_id=subject_id,
                    classroom=classroom,
                    term=term,
                    academic_year=academic_year,
                )
                created += int(was_created)
        return Response({'created': created})
    