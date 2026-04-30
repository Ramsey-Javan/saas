import logging
from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django_filters.rest_framework import DjangoFilterBackend
from .models import SMSLog
from .serializers import SMSLogSerializer, SendSMSSerializer, BulkSMSSerializer
from apps.authentication.permissions import IsAdminRole, IsTeacherOrAdmin

logger = logging.getLogger(__name__)


class SMSLogListView(generics.ListAPIView):
    serializer_class = SMSLogSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'student']
    search_fields = ['recipient_phone', 'message', 'message_id']
    ordering = ['-created_at']
    queryset = SMSLog.objects.select_related('student', 'sent_by').all()


class SMSLogDetailView(generics.RetrieveAPIView):
    serializer_class = SMSLogSerializer
    permission_classes = [IsAdminRole]
    queryset = SMSLog.objects.all()


class SendSMSView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(request=SendSMSSerializer, responses={201: OpenApiResponse(description='SMS sent')})
    def post(self, request):
        serializer = SendSMSSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        student = None
        if data.get('student_id'):
            from apps.students.models import Student
            try:
                student = Student.objects.get(pk=data['student_id'])
            except Student.DoesNotExist:
                return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

        from .africastalking import AfricasTalkingService
        service = AfricasTalkingService()
        try:
            logs = service.send_sms_and_log(
                data['phone_numbers'],
                data['message'],
                student=student,
                sent_by=request.user,
            )
        except Exception as exc:
            logger.error('SMS send failed: %s', exc)
            return Response({'detail': 'SMS sending failed.'}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'detail': f'{len(logs)} SMS queued/sent.',
            'sms_log_ids': [log.id for log in logs],
        }, status=status.HTTP_201_CREATED)


class BulkSMSView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(request=BulkSMSSerializer, responses={200: OpenApiResponse(description='Bulk SMS queued')})
    def post(self, request):
        serializer = BulkSMSSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        from apps.students.models import Student
        from .tasks import send_bulk_sms

        student_qs = Student.objects.filter(is_active=True).exclude(parent_phone='')
        if data.get('grade_level'):
            student_qs = student_qs.filter(grade_level=data['grade_level'])

        if data['send_to'] == 'debtors':
            from apps.fees.models import FeePayment
            from django.db.models import Sum
            from decimal import Decimal

            paid_student_ids = (
                FeePayment.objects.filter(
                    term=data.get('term', ''),
                    academic_year=data.get('academic_year', ''),
                    status='completed',
                )
                .values('student_id')
                .annotate(total_paid=Sum('amount_paid'))
            )
            paid_map = {p['student_id']: p['total_paid'] for p in paid_student_ids}
            student_qs = student_qs.exclude(id__in=[sid for sid, amt in paid_map.items() if amt and amt > 0])

        phones = list(student_qs.values_list('parent_phone', flat=True))
        if not phones:
            return Response({'detail': 'No recipients found.'}, status=status.HTTP_400_BAD_REQUEST)

        send_bulk_sms.delay(phones, data['message'], sent_by_id=request.user.id)

        return Response({
            'detail': f'Bulk SMS queued for {len(phones)} recipients.',
            'recipient_count': len(phones),
        })
