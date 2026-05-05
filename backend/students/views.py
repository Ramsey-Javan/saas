from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.http import HttpResponse
import csv
from .utils import parse_student_csv, promote_all_students_to_next_grade

from accounts.views import IsSchoolAdmin, IsTeacher
from rest_framework.permissions import IsAuthenticated

from .models import Student, Guardian, Classroom
from .serializers import (
    ClassroomSerializer,
    GuardianSerializer,
    StudentListSerializer,
    StudentDetailSerializer,
)


# ─── Classrooms ───────────────────────────────────────────────────────────────

class ClassroomListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/students/classrooms/          → list all classrooms
    POST /api/students/classrooms/          → create classroom (admin only)
    """
    serializer_class = ClassroomSerializer
    pagination_class = None

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsSchoolAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Classroom.objects.select_related('class_teacher')
        if getattr(self.request.user, 'tenant_id', None):
            qs = qs.filter(tenant=self.request.user.tenant)
        year = self.request.query_params.get('year')
        grade = self.request.query_params.get('grade')
        if year:
            qs = qs.filter(academic_year=year)
        if grade:
            qs = qs.filter(grade_level=grade)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class ClassroomDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/students/classrooms/<id>/
    PATCH  /api/students/classrooms/<id>/
    DELETE /api/students/classrooms/<id>/
    """
    serializer_class = ClassroomSerializer
    permission_classes = [IsSchoolAdmin]

    def get_queryset(self):
        qs = Classroom.objects.all()
        if getattr(self.request.user, 'tenant_id', None):
            qs = qs.filter(tenant=self.request.user.tenant)
        return qs


class ClassroomStudentsView(generics.ListAPIView):
    """
    GET /api/students/classrooms/<id>/students/
    Returns all students in a specific classroom.
    """
    serializer_class = StudentListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Student.objects.filter(
            classroom_id=self.kwargs['pk'],
            is_active=True,
        ).select_related('primary_guardian', 'classroom')
        if getattr(self.request.user, 'tenant_id', None):
            qs = qs.filter(tenant=self.request.user.tenant)
        return qs


# ─── Guardians ────────────────────────────────────────────────────────────────

class GuardianListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/students/guardians/
    POST /api/students/guardians/
    """
    serializer_class = GuardianSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name', 'last_name', 'phone', 'national_id']

    def get_queryset(self):
        return Guardian.objects.all()


class GuardianDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/students/guardians/<id>/
    PATCH  /api/students/guardians/<id>/
    DELETE /api/students/guardians/<id>/
    """
    serializer_class = GuardianSerializer
    permission_classes = [IsSchoolAdmin]
    queryset = Guardian.objects.all()


# ─── Students ─────────────────────────────────────────────────────────────────

class StudentListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/students/                     → paginated list with search/filter
    POST /api/students/                     → admit new student
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['first_name', 'last_name', 'admission_number', 'nemis_no']
    filterset_fields = ['classroom', 'gender', 'status', 'classroom__grade_level']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsSchoolAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StudentDetailSerializer
        return StudentListSerializer

    def get_queryset(self):
        qs = Student.objects.select_related(
            'classroom', 'primary_guardian'
        ).order_by('-created_at')
        if getattr(self.request.user, 'tenant_id', None):
            qs = qs.filter(tenant=self.request.user.tenant)
        # Filter inactive/transferred unless explicitly requested
        show_all = self.request.query_params.get('show_all', 'false').lower() == 'true'
        if not show_all:
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class StudentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/students/<id>/
    PATCH  /api/students/<id>/
    DELETE /api/students/<id>/   → sets is_active=False (soft delete)
    """
    serializer_class = StudentDetailSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method in ['PATCH', 'PUT', 'DELETE']:
            return [IsSchoolAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Student.objects.select_related('classroom', 'primary_guardian').order_by('-created_at')
        if getattr(self.request.user, 'tenant_id', None):
            qs = qs.filter(tenant=self.request.user.tenant)
        return qs

    def perform_update(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

    def destroy(self, request, *args, **kwargs):
        student = self.get_object()
        student.is_active = False
        student.status = Student.Status.DROPPED
        student.save(update_fields=['is_active', 'status', 'updated_at'])
        return Response({'detail': 'Student archived as dropped.'}, status=status.HTTP_200_OK)


class StudentSearchView(APIView):
    """
    GET /api/students/search/?q=kamau
    Quick search used for fee assignment, attendance, etc.
    Returns lightweight results.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response([])

        students = Student.objects.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(admission_number__icontains=q),
            is_active=True,
        ).select_related('classroom', 'primary_guardian')[:10]

        return Response(StudentListSerializer(students, many=True).data)


class StudentTransferView(APIView):
    """
    POST /api/students/<id>/transfer/
    Body: { "classroom": <id> }
    Moves student to a different class.
    """
    permission_classes = [IsSchoolAdmin]

    def post(self, request, pk):
        students = Student.objects.all()
        classrooms = Classroom.objects.all()
        if getattr(request.user, 'tenant_id', None):
            students = students.filter(tenant=request.user.tenant)
            classrooms = classrooms.filter(tenant=request.user.tenant)

        try:
            student = students.get(pk=pk)
        except Student.DoesNotExist:
            return Response({'detail': 'Student not found.'}, status=404)

        classroom_id = request.data.get('classroom')
        try:
            classroom = classrooms.get(pk=classroom_id)
        except Classroom.DoesNotExist:
            return Response({'detail': 'Classroom not found.'}, status=400)

        old_class = str(student.classroom)
        student.classroom = classroom
        student.save()

        return Response({
            'detail': f'{student.get_full_name()} moved from {old_class} to {classroom}.',
            'student': StudentDetailSerializer(student).data,
        })


class StudentArchiveView(APIView):
    """
    POST /api/students/<id>/archive/
    Body: { "status": "active" | "transferred" | "graduated" | "dropped" }
    Updates a student's lifecycle status without deleting their record.
    """
    permission_classes = [IsSchoolAdmin]

    allowed_statuses = {
        Student.Status.ACTIVE,
        Student.Status.TRANSFERRED,
        Student.Status.GRADUATED,
        Student.Status.DROPPED,
    }

    def post(self, request, pk):
        students = Student.objects.all()
        if getattr(request.user, 'tenant_id', None):
            students = students.filter(tenant=request.user.tenant)

        try:
            student = students.get(pk=pk)
        except Student.DoesNotExist:
            return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

        lifecycle_status = request.data.get('status')
        if lifecycle_status not in self.allowed_statuses:
            return Response(
                {'detail': 'Invalid student status.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student.status = lifecycle_status
        student.is_active = lifecycle_status == Student.Status.ACTIVE
        student.save(update_fields=['status', 'is_active', 'updated_at'])

        return Response({
            'detail': f'Student status changed to {student.get_status_display().lower()}.',
            'student': StudentDetailSerializer(student).data,
        })


class StudentPromoteAllView(APIView):
    """
    POST /api/students/promote-all/
    Body: { "confirm": true }
    Promotes active students to the next grade within the current tenant.
    """
    permission_classes = [IsSchoolAdmin]

    def post(self, request):
        if request.data.get('confirm') is not True:
            return Response(
                {'detail': 'Promotion confirmation is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = promote_all_students_to_next_grade(request.user.tenant)

        return Response({
            'detail': 'Student promotion completed.',
            **result,
        })


class StudentBulkImportView(APIView):
    """
    POST /api/students/bulk-import/
    Bulk import students from a CSV file.
    """
    permission_classes = [IsSchoolAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        csv_file = request.FILES['file']

        if not csv_file.name.lower().endswith('.csv'):
            return Response(
                {'error': 'File must be a CSV'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = parse_student_csv(csv_file, request.user.tenant)

        if result['errors']:
            return Response({
                'success_count': result['success_count'],
                'total_errors': len(result['errors']),
                'errors': result['errors'][:10],
                'message': f'Successfully imported {result["success_count"]} students. {len(result["errors"])} errors occurred.',
            }, status=status.HTTP_207_MULTI_STATUS)

        return Response({
            'success_count': result['success_count'],
            'message': f'Successfully imported {result["success_count"]} students.',
        })


class StudentImportTemplateView(APIView):
    """
    GET /api/students/import-template/
    Download CSV template for bulk import.
    """
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="student_import_template.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'admission_number', 'first_name', 'middle_name', 'last_name',
            'gender', 'date_of_birth', 'classroom_name',
            'guardian_first_name', 'guardian_last_name', 'guardian_phone',
            'guardian_relationship', 'guardian_national_id',
            'nemis_no', 'birth_certificate_no', 'blood_group', 'medical_notes',
        ])
        writer.writerow([
            'ADM/2024/001', 'Amani', '', 'Kamau',
            'M', '2015-03-15', 'Grade 5 East',
            'John', 'Kamau', '0722000000',
            'father', '12345678',
            '', '', '', '',
        ])

        return response
