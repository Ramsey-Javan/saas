from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from .models import Student, Admission
from .serializers import (
    StudentListSerializer,
    StudentDetailSerializer,
    StudentCreateUpdateSerializer,
    AdmissionSerializer,
)
from apps.authentication.permissions import IsTeacherOrAdmin, IsAdminRole


class StudentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['grade_level', 'stream', 'gender', 'is_active']
    search_fields = ['first_name', 'last_name', 'admission_number', 'parent_phone']
    ordering_fields = ['last_name', 'first_name', 'admission_number', 'grade_level', 'created_at']
    ordering = ['last_name', 'first_name']

    def get_queryset(self):
        return Student.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StudentCreateUpdateSerializer
        return StudentListSerializer


class StudentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsTeacherOrAdmin]
    queryset = Student.objects.all()

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return StudentCreateUpdateSerializer
        return StudentDetailSerializer


class StudentByAdmissionView(generics.RetrieveAPIView):
    permission_classes = [IsTeacherOrAdmin]
    serializer_class = StudentDetailSerializer
    queryset = Student.objects.all()
    lookup_field = 'admission_number'


class AdmissionListCreateView(generics.ListCreateAPIView):
    serializer_class = AdmissionSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['student', 'academic_year', 'admission_type', 'status']
    ordering = ['-date_admitted']

    def get_queryset(self):
        return Admission.objects.select_related('student', 'admitted_by').all()


class AdmissionDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AdmissionSerializer
    permission_classes = [IsAdminRole]
    queryset = Admission.objects.all()


class StudentAdmissionsView(generics.ListAPIView):
    serializer_class = AdmissionSerializer
    permission_classes = [IsTeacherOrAdmin]
    queryset = Admission.objects.none()

    def get_queryset(self):
        return Admission.objects.filter(student_id=self.kwargs['student_id'])


class GradeLevelStatsView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(responses={200: OpenApiResponse(description='Grade level statistics')})
    def get(self, request):
        from .models import GRADE_CHOICES

        stats = (
            Student.objects.filter(is_active=True)
            .values('grade_level')
            .annotate(
                total=Count('id'),
                male=Count('id', filter=Q(gender='M')),
                female=Count('id', filter=Q(gender='F')),
            )
            .order_by('grade_level')
        )

        grade_map = dict(GRADE_CHOICES)
        result = [
            {
                'grade_level': s['grade_level'],
                'grade_display': grade_map.get(s['grade_level'], s['grade_level']),
                'total': s['total'],
                'male': s['male'],
                'female': s['female'],
            }
            for s in stats
        ]
        return Response(result)
