import csv
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CustomUser
from accounts.views import IsSchoolAdmin, IsTeacher
from finance.models import CONFIRMED_PAYMENT_STATUSES, FeeStructure, Payment, StudentFee
from finance.utils import calculate_waived_amount, get_sibling_discount

from academics.models import ClassSubjectAssignment

from .models import Classroom, Guardian, Student
from .serializers import (
    ClassroomSerializer,
    GuardianSerializer,
    StudentDetailSerializer,
    StudentListSerializer,
)
from .utils import parse_student_csv, promote_all_students_to_next_grade

PLAN_LIMITS = {
    'trial': 100,
    'starter': 400,
    'growth': 1000,
    'enterprise': None,
}


def _teacher_accessible_classroom_ids(user):
    """
    Classrooms a teacher may see students in: where they are the homeroom
    (class_teacher) OR where they have a ClassSubjectAssignment. Used to
    scope the student list/detail views so a teacher doesn't see every
    student in the school — only students in classes they're actually
    connected to.
    """
    homeroom_ids = set(
        Classroom.objects.filter(tenant=user.tenant, class_teacher=user).values_list('id', flat=True)
    )
    subject_ids = set(
        ClassSubjectAssignment.objects.filter(tenant=user.tenant, teacher=user).values_list('classroom_id', flat=True)
    )
    return homeroom_ids | subject_ids


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
        class_teacher_id = self.request.query_params.get('class_teacher')
        if year:
            qs = qs.filter(academic_year=year)
        if grade:
            qs = qs.filter(grade_level=grade)
        if class_teacher_id:
            qs = qs.filter(class_teacher_id=class_teacher_id)
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

    def get_permissions(self):
        if self.request.method in ['PATCH', 'PUT', 'DELETE']:
            return [IsSchoolAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Classroom.objects.all()
        if getattr(self.request.user, 'tenant_id', None):
            qs = qs.filter(tenant=self.request.user.tenant)
        return qs

    def destroy(self, request, *args, **kwargs):
        classroom = self.get_object()
        student_count = classroom.students.filter(is_active=True).count()
        if student_count > 0:
            return Response(
                {
                    'detail': (
                        f'Cannot delete {classroom} — it still has {student_count} '
                        f'active student{"s" if student_count != 1 else ""} assigned. '
                        f'Transfer them to another classroom first.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class ClassroomStudentsView(generics.ListAPIView):
    """
    GET /api/students/classrooms/<id>/students/
    Returns all students in a specific classroom.
    """
    serializer_class = StudentListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

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
        qs = Guardian.objects.all()
        if getattr(self.request.user, 'tenant_id', None):
            qs = qs.filter(tenant=self.request.user.tenant)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class GuardianDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/students/guardians/<id>/
    PATCH  /api/students/guardians/<id>/
    DELETE /api/students/guardians/<id>/
    """
    serializer_class = GuardianSerializer
    permission_classes = [IsSchoolAdmin]

    def get_queryset(self):
        qs = Guardian.objects.all()
        if getattr(self.request.user, 'tenant_id', None):
            qs = qs.filter(tenant=self.request.user.tenant)
        return qs


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
        if getattr(self.request.user, 'role', None) == 'teacher':
            qs = qs.filter(classroom_id__in=_teacher_accessible_classroom_ids(self.request.user))
        
        show_all = self.request.query_params.get('show_all', 'false').lower() == 'true'
        if not show_all:
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        limit = PLAN_LIMITS.get(tenant.plan)
        if limit is not None:
            current_count = Student.objects.filter(tenant=tenant, is_active=True).count()
            if current_count >= limit:
                raise ValidationError({
                    'detail': (
                        f'Your {tenant.get_plan_display()} plan allows up to {limit} students. '
                        f'You currently have {current_count}. Upgrade your plan to add more students.'
                    )
                })
        serializer.save(tenant=tenant)


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
        if getattr(self.request.user, 'role', None) == 'teacher':
            qs = qs.filter(classroom_id__in=_teacher_accessible_classroom_ids(self.request.user))
        return qs

    def perform_update(self, serializer):
        user = self.request.user
        if getattr(user, 'role', None) == 'teacher':
            student = self.get_object()
            if student.classroom_id not in _teacher_accessible_classroom_ids(user):
                raise PermissionDenied({"detail": "You do not have permission to modify this student."})
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

        qs = Student.objects.all()
        if getattr(request.user, 'tenant_id', None):
            qs = qs.filter(tenant=request.user.tenant)

        students = qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(admission_number__icontains=q),
            is_active=True,
        ).select_related('classroom', 'primary_guardian')[:10]

        return Response(StudentListSerializer(students, many=True).data)


def _recalculate_invoice(invoice):
    if not invoice:
        return None

    money_zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
    total_paid = (
        Payment.objects.filter(student_fee=invoice, status__in=CONFIRMED_PAYMENT_STATUSES)
        .aggregate(total=Coalesce(Sum('amount'), money_zero))
        .get('total')
        or Decimal('0.00')
    )
    total_due = max(
        Decimal('0.00'),
        invoice.expected_amount + invoice.carried_forward + invoice.penalty_amount - invoice.waived_amount,
    )

    invoice.paid_amount = min(total_paid, total_due)
    invoice.credit = max(Decimal('0.00'), total_paid - total_due)
    if invoice.paid_amount >= total_due:
        invoice.status = 'paid'
    elif invoice.paid_amount > 0:
        invoice.status = 'partial'
    else:
        invoice.status = 'unpaid'

    invoice.save(update_fields=['paid_amount', 'credit', 'status', 'updated_at'])
    return invoice


def _sync_transfer_invoice(student, new_classroom, tenant):
    current_invoice = (
        StudentFee.objects.filter(student=student, tenant=tenant)
        .select_related('fee_structure')
        .order_by('-fee_structure__academic_year', '-fee_structure__term')
        .first()
    )
    if not current_invoice:
        return None

    term = current_invoice.fee_structure.term
    academic_year = current_invoice.fee_structure.academic_year
    try:
        new_structure = FeeStructure.objects.get(
            tenant=tenant,
            classroom=new_classroom,
            term=term,
            academic_year=academic_year,
            is_active=True,
        )
    except FeeStructure.DoesNotExist:
        return current_invoice

    if current_invoice.fee_structure_id == new_structure.id:
        return current_invoice

    target_invoice = current_invoice
    existing_invoice = StudentFee.objects.filter(
        student=student,
        tenant=tenant,
        fee_structure=new_structure,
    ).first()
    if existing_invoice and existing_invoice.id != current_invoice.id:
        Payment.objects.filter(student_fee=current_invoice).update(student_fee=existing_invoice)
        current_invoice.delete()
        target_invoice = existing_invoice
    else:
        target_invoice.fee_structure = new_structure

    waived_amount, waiver = calculate_waived_amount(student, new_structure.base_amount, term, academic_year)
    if waived_amount == 0:
        sibling_policy = get_sibling_discount(student)
        if sibling_policy:
            if sibling_policy.discount_type == 'percentage':
                waived_amount = new_structure.base_amount * (sibling_policy.discount_value / Decimal('100'))
            else:
                waived_amount = min(sibling_policy.discount_value, new_structure.base_amount)
            waived_amount = waived_amount.quantize(Decimal('0.01'))

    target_invoice.expected_amount = new_structure.base_amount
    target_invoice.waived_amount = waived_amount
    target_invoice.waiver = waiver
    if new_structure.due_date:
        target_invoice.due_date = new_structure.due_date

    target_invoice.save(update_fields=[
        'fee_structure',
        'expected_amount',
        'waived_amount',
        'waiver',
        'due_date',
        'updated_at',
    ])
    _recalculate_invoice(target_invoice)
    return target_invoice


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
        with transaction.atomic():
            student.classroom = classroom
            student.save(update_fields=['classroom', 'updated_at'])
            _sync_transfer_invoice(student, classroom, request.user.tenant)

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

        # Log the bulk promotion activity
        from activity.models import ActivityLog
        from activity.utils import log_activity

        log_activity(
            tenant=request.user.tenant,
            activity_type=ActivityLog.ActivityType.STUDENT_PROMOTED,
            title="Bulk student promotion completed",
            description=(
                f"Promoted {result.get('promoted_count', 0)} students, "
                f"graduated {result.get('graduated_count', 0)}, "
                f"skipped {result.get('skipped_count', 0)}"
            ),
            actor=request.user,
            metadata={
                'promoted': result.get('promoted_count', 0),
                'graduated': result.get('graduated_count', 0),
                'skipped': result.get('skipped_count', 0),
            },
        )

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


# ─── Classroom Homeroom Assignment ───────────────────────────────────────────

class AssignClassTeacherView(APIView):
    """
    POST /api/students/classrooms/<id>/assign-class-teacher/
    Body: { "teacher_id": <CustomUser id> }
    Sets Classroom.class_teacher.
    """
    permission_classes = [IsSchoolAdmin]

    def post(self, request, pk):
        tenant = request.user.tenant
        try:
            classroom = Classroom.objects.get(pk=pk, tenant=tenant)
        except Classroom.DoesNotExist:
            return Response({'detail': 'Classroom not found.'}, status=status.HTTP_404_NOT_FOUND)

        teacher_id = request.data.get('teacher_id')
        if not teacher_id:
            return Response({'detail': 'teacher_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            teacher = CustomUser.objects.get(pk=teacher_id, tenant=tenant, role=CustomUser.Role.TEACHER)
        except CustomUser.DoesNotExist:
            return Response(
                {'detail': 'That user is not a teacher in this school.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_teacher_name = classroom.class_teacher.get_full_name() if classroom.class_teacher else None
        classroom.class_teacher = teacher
        classroom.save(update_fields=['class_teacher'])

        return Response({
            'detail': (
                f'{teacher.get_full_name()} assigned as class teacher for {classroom}.'
                + (f' (Previously: {previous_teacher_name})' if previous_teacher_name else '')
            ),
            'classroom': ClassroomSerializer(classroom).data,
        })


class UnassignClassTeacherView(APIView):
    """
    POST /api/students/classrooms/<id>/unassign-class-teacher/
    Clears Classroom.class_teacher.
    """
    permission_classes = [IsSchoolAdmin]

    def post(self, request, pk):
        tenant = request.user.tenant
        try:
            classroom = Classroom.objects.get(pk=pk, tenant=tenant)
        except Classroom.DoesNotExist:
            return Response({'detail': 'Classroom not found.'}, status=status.HTTP_404_NOT_FOUND)

        classroom.class_teacher = None
        classroom.save(update_fields=['class_teacher'])
        return Response({
            'detail': f'Class teacher removed from {classroom}.',
            'classroom': ClassroomSerializer(classroom).data,
        })