"""Waiver policy and student waiver viewsets."""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from students.models import Student

from ..models import StudentFee, StudentWaiver, WaiverPolicy
from ..permissions import IsAdminOrBursar
from ..serializers import StudentWaiverSerializer, WaiverPolicySerializer
from ..utils import apply_waiver_to_invoices, remove_waiver_from_invoices
from .mixins import TenantScopedMixin


class WaiverPolicyViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = WaiverPolicy.objects.all()
    serializer_class = WaiverPolicySerializer
    permission_classes = [IsAdminOrBursar]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['description']

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """
        Get active waiver policies with student counts for dashboard.
        Returns list of policies with number of students assigned to each.
        """
        tenant = request.user.tenant

        policies = WaiverPolicy.objects.filter(
            tenant=tenant,
            is_active=True,
        ).annotate(
            student_count=Count('student_waivers', filter=Q(student_waivers__is_active=True))
        ).values(
            'id', 'category', 'discount_type', 'discount_value', 'description', 'student_count', 'is_active', 'created_at'
        ).order_by('-created_at')

        return Response({
            'count': len(policies),
            'results': list(policies),
        })


class StudentWaiverViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = StudentWaiver.objects.select_related('student', 'policy', 'approved_by')
    serializer_class = StudentWaiverSerializer
    permission_classes = [IsAdminOrBursar]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['student__id', 'policy__category', 'is_active']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']

    def create(self, request, *args, **kwargs):
        """
        Assigning the same waiver again should reactivate the existing assignment.
        Otherwise old inactive rows hit the unique constraint and the dashboard
        keeps showing zero active students for that policy.
        """
        tenant = request.user.tenant
        student_id = request.data.get('student')
        policy_id = request.data.get('policy')

        if student_id and policy_id:
            student = Student.objects.filter(id=student_id, tenant=tenant).first()
            policy = WaiverPolicy.objects.filter(id=policy_id, tenant=tenant).first()
            if not student or not policy:
                raise ValidationError({'detail': 'Student or waiver policy was not found for this school.'})

            existing = StudentWaiver.objects.filter(
                tenant=tenant,
                student_id=student_id,
                policy_id=policy_id,
            ).first()
            if existing:
                data = request.data.copy()
                data['is_active'] = True
                serializer = self.get_serializer(existing, data=data, partial=True)
                serializer.is_valid(raise_exception=True)
                waiver = serializer.save(
                    tenant=tenant,
                    approved_by=request.user,
                    approved_on=timezone.localdate(),
                    is_active=True,
                )
                transaction.on_commit(lambda: apply_waiver_to_invoices(waiver))
                return Response(serializer.data, status=status.HTTP_200_OK)

        data = request.data.copy()
        data['is_active'] = True
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        waiver = serializer.save(
            tenant=self.request.user.tenant,
            approved_by=self.request.user,
            approved_on=timezone.localdate(),
            is_active=True,
        )
        transaction.on_commit(lambda: apply_waiver_to_invoices(waiver))

    def perform_update(self, serializer):
        waiver = serializer.save()
        transaction.on_commit(lambda: apply_waiver_to_invoices(waiver) if waiver.is_active else remove_waiver_from_invoices(waiver))

    def perform_destroy(self, instance):
        remove_waiver_from_invoices(instance)
        instance.delete()

    @action(detail=False, methods=['get'])
    def report(self, request):
        """
        Get waiver report summary.
        Returns total students with waivers, total waived amount this term.
        """
        tenant = request.user.tenant

        total_students_with_waivers = StudentWaiver.objects.filter(
            tenant=tenant,
            is_active=True,
        ).values('student_id').distinct().count()

        # Sum of all active waivers' applied amounts (estimated from StudentFee.waived_amount)
        total_waived = StudentFee.objects.filter(
            tenant=tenant,
            waiver__isnull=False,
        ).aggregate(total=Sum('waived_amount'))['total'] or Decimal('0.00')

        return Response({
            'total_students_with_waivers': total_students_with_waivers,
            'total_waived_amount': str(total_waived),
        })

    @action(detail=False, methods=['get'])
    def by_policy(self, request):
        """
        Get waivers by policy ID.
        Query param: policy_id (required)
        Returns list of students with waivers for the given policy.
        """
        policy_id = request.query_params.get('policy_id')
        if not policy_id:
            return Response({'error': 'policy_id query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = request.user.tenant
        try:
            waivers = StudentWaiver.objects.select_related(
                'student', 'policy', 'approved_by'
            ).filter(
                tenant=tenant,
                policy_id=policy_id,
                is_active=True,
            ).order_by('-created_at')

            serializer = StudentWaiverSerializer(
                waivers,
                many=True,
                context={'request': request},
            )
            return Response({
                'count': waivers.count(),
                'results': serializer.data,
            })
        except Exception as err:
            return Response({'error': str(err)}, status=status.HTTP_400_BAD_REQUEST)
