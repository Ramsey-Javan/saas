"""Curriculum and subject assignment viewsets."""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..models import (
    ClassSubjectAssignment,
    LearningOutcome,
    Strand,
    Subject,
    SubStrand,
)
from ..permissions import IsAdminUser, IsTeacherOrAdmin
from ..serializers import (
    ClassSubjectAssignmentSerializer,
    LearningOutcomeSerializer,
    StrandSerializer,
    SubjectListSerializer,
    SubjectSerializer,
    SubStrandSerializer,
)
from ..utils import load_knec_curriculum
from .mixins import TenantScopedMixin, _is_teacher, _teacher_subject_ids


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
