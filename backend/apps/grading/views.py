from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django_filters.rest_framework import DjangoFilterBackend
from .models import Subject, Assessment, ReportCard
from .serializers import (
    SubjectSerializer,
    AssessmentSerializer,
    AssessmentBulkSerializer,
    ReportCardSerializer,
)
from apps.authentication.permissions import IsTeacherOrAdmin, IsAdminRole


class SubjectListCreateView(generics.ListCreateAPIView):
    serializer_class = SubjectSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['grade_level', 'is_active']
    search_fields = ['name', 'code']
    queryset = Subject.objects.all()


class SubjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SubjectSerializer
    permission_classes = [IsAdminRole]
    queryset = Subject.objects.all()


class AssessmentListCreateView(generics.ListCreateAPIView):
    serializer_class = AssessmentSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['student', 'subject', 'term', 'academic_year', 'assessment_type', 'competency']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']
    ordering = ['-assessment_date']

    def get_queryset(self):
        return Assessment.objects.select_related('student', 'subject', 'recorded_by').all()


class AssessmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AssessmentSerializer
    permission_classes = [IsTeacherOrAdmin]
    queryset = Assessment.objects.all()


class BulkAssessmentCreateView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(request=AssessmentBulkSerializer, responses={201: OpenApiResponse(description='Assessments saved')})
    def post(self, request):
        serializer = AssessmentBulkSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            objs = serializer.save()
            return Response(
                {'detail': f'{len(objs)} assessments saved successfully.'},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentAssessmentsView(generics.ListAPIView):
    serializer_class = AssessmentSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['term', 'academic_year', 'subject', 'assessment_type']
    queryset = Assessment.objects.none()

    def get_queryset(self):
        return Assessment.objects.filter(student_id=self.kwargs['student_id']).select_related('subject')


class ReportCardListCreateView(generics.ListCreateAPIView):
    serializer_class = ReportCardSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['term', 'academic_year', 'status']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']

    def get_queryset(self):
        return ReportCard.objects.select_related('student', 'generated_by').all()


class ReportCardDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ReportCardSerializer
    permission_classes = [IsTeacherOrAdmin]
    queryset = ReportCard.objects.all()


class StudentReportCardsView(generics.ListAPIView):
    serializer_class = ReportCardSerializer
    permission_classes = [IsTeacherOrAdmin]
    queryset = ReportCard.objects.none()

    def get_queryset(self):
        return ReportCard.objects.filter(student_id=self.kwargs['student_id'])
