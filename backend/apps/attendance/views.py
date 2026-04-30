from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from .models import AttendanceRecord
from .serializers import (
    AttendanceRecordSerializer,
    BulkAttendanceSerializer,
    AttendanceSummarySerializer,
)
from apps.authentication.permissions import IsTeacherOrAdmin
from apps.students.models import Student


class AttendanceListCreateView(generics.ListCreateAPIView):
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['student', 'date', 'status', 'recorded_by']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']
    ordering = ['-date']

    def get_queryset(self):
        return AttendanceRecord.objects.select_related('student', 'recorded_by').all()


class AttendanceDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsTeacherOrAdmin]
    queryset = AttendanceRecord.objects.all()


class BulkAttendanceView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(request=BulkAttendanceSerializer, responses={200: OpenApiResponse(description='Attendance saved')})
    def post(self, request):
        serializer = BulkAttendanceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        date = serializer.validated_data['date']
        records = serializer.validated_data['records']
        user = request.user
        created = 0
        updated = 0

        for record in records:
            obj, created_flag = AttendanceRecord.objects.update_or_create(
                student_id=record['student_id'],
                date=date,
                defaults={
                    'status': record['status'],
                    'remarks': record.get('remarks', ''),
                    'recorded_by': user,
                },
            )
            if created_flag:
                created += 1
            else:
                updated += 1

        return Response(
            {'detail': f'{created} created, {updated} updated for {date}.'},
            status=status.HTTP_200_OK,
        )


class StudentAttendanceView(generics.ListAPIView):
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering = ['-date']
    queryset = AttendanceRecord.objects.none()

    def get_queryset(self):
        return AttendanceRecord.objects.filter(student_id=self.kwargs['student_id'])


class AttendanceSummaryView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(responses={200: OpenApiResponse(description='Attendance summary per student')})
    def get(self, request):
        grade_level = request.query_params.get('grade_level')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        student_qs = Student.objects.filter(is_active=True)
        if grade_level:
            student_qs = student_qs.filter(grade_level=grade_level)

        att_qs = AttendanceRecord.objects.filter(student__in=student_qs)
        if start_date:
            att_qs = att_qs.filter(date__gte=start_date)
        if end_date:
            att_qs = att_qs.filter(date__lte=end_date)

        summary = (
            att_qs.values('student__id', 'student__first_name', 'student__last_name', 'student__admission_number')
            .annotate(
                total_days=Count('id'),
                present=Count('id', filter=Q(status='present')),
                absent=Count('id', filter=Q(status='absent')),
                late=Count('id', filter=Q(status='late')),
                excused=Count('id', filter=Q(status='excused')),
                half_day=Count('id', filter=Q(status='half_day')),
            )
        )

        result = []
        for s in summary:
            total = s['total_days'] or 1
            present = s['present']
            result.append({
                'student_id': s['student__id'],
                'student_name': f"{s['student__first_name']} {s['student__last_name']}",
                'admission_number': s['student__admission_number'],
                'total_days': s['total_days'],
                'present': present,
                'absent': s['absent'],
                'late': s['late'],
                'excused': s['excused'],
                'half_day': s['half_day'],
                'attendance_percentage': round((present / total) * 100, 1),
            })

        return Response(result)


class DailyAttendanceView(generics.ListAPIView):
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']
    queryset = AttendanceRecord.objects.none()

    def get_queryset(self):
        date = self.kwargs['date']
        grade_level = self.request.query_params.get('grade_level')
        qs = AttendanceRecord.objects.filter(date=date).select_related('student')
        if grade_level:
            qs = qs.filter(student__grade_level=grade_level)
        return qs
