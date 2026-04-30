import logging
from decimal import Decimal
from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum
from .models import FeeStructure, FeePayment, MpesaTransaction
from .serializers import (
    FeeStructureSerializer,
    FeePaymentSerializer,
    FeePaymentCreateSerializer,
    MpesaTransactionSerializer,
    StkPushSerializer,
)
from apps.authentication.permissions import IsAdminRole, IsAccountantOrAdmin, IsTeacherOrAdmin
from apps.students.models import Student

logger = logging.getLogger(__name__)


class FeeStructureListCreateView(generics.ListCreateAPIView):
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAccountantOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['grade_level', 'term', 'academic_year', 'fee_type', 'is_mandatory']
    ordering = ['academic_year', 'term', 'grade_level', 'fee_type']
    queryset = FeeStructure.objects.all()


class FeeStructureDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAccountantOrAdmin]
    queryset = FeeStructure.objects.all()


class FeePaymentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAccountantOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['student', 'term', 'academic_year', 'payment_method', 'status']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number', 'transaction_ref']
    ordering = ['-payment_date']

    def get_queryset(self):
        return FeePayment.objects.select_related('student', 'fee_structure').all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return FeePaymentCreateSerializer
        return FeePaymentSerializer


class FeePaymentDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAccountantOrAdmin]
    queryset = FeePayment.objects.all()

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return FeePaymentCreateSerializer
        return FeePaymentSerializer


class StudentPaymentsView(generics.ListAPIView):
    serializer_class = FeePaymentSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['term', 'academic_year', 'status']
    queryset = FeePayment.objects.none()

    def get_queryset(self):
        return FeePayment.objects.filter(student_id=self.kwargs['student_id'])


class StkPushView(APIView):
    permission_classes = [IsAccountantOrAdmin]

    @extend_schema(request=StkPushSerializer, responses={201: OpenApiResponse(description='STK Push initiated')})
    def post(self, request):
        serializer = StkPushSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            student = Student.objects.get(pk=data['student_id'])
        except Student.DoesNotExist:
            return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

        from .mpesa import MpesaService
        mpesa = MpesaService()

        try:
            response = mpesa.stk_push(
                phone_number=data['phone_number'],
                amount=data['amount'],
                account_reference=data['account_reference'],
                transaction_desc=data['transaction_desc'],
            )
        except Exception as exc:
            logger.error('STK Push error: %s', exc)
            return Response({'detail': 'M-Pesa request failed. Please try again.'}, status=status.HTTP_502_BAD_GATEWAY)

        transaction = MpesaTransaction.objects.create(
            phone_number=data['phone_number'],
            amount=data['amount'],
            merchant_request_id=response.get('MerchantRequestID', ''),
            checkout_request_id=response.get('CheckoutRequestID', ''),
            status='pending',
            student=student,
            account_reference=data['account_reference'],
        )

        return Response({
            'detail': 'STK Push initiated. Please check your phone.',
            'checkout_request_id': transaction.checkout_request_id,
            'transaction_id': transaction.id,
        }, status=status.HTTP_201_CREATED)


class MpesaCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(exclude=True)
    def post(self, request):
        try:
            body = request.data.get('Body', {})
            callback = body.get('stkCallback', {})
            checkout_request_id = callback.get('CheckoutRequestID', '')
            result_code = callback.get('ResultCode')
            result_desc = callback.get('ResultDesc', '')

            try:
                txn = MpesaTransaction.objects.get(checkout_request_id=checkout_request_id)
            except MpesaTransaction.DoesNotExist:
                logger.warning('Callback for unknown CheckoutRequestID: %s', checkout_request_id)
                return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})

            txn.result_code = result_code
            txn.result_desc = result_desc

            if result_code == 0:
                txn.status = 'success'
                metadata_items = callback.get('CallbackMetadata', {}).get('Item', [])
                meta = {item['Name']: item.get('Value') for item in metadata_items}
                txn.mpesa_receipt_number = str(meta.get('MpesaReceiptNumber', ''))
                txn.transaction_date = str(meta.get('TransactionDate', ''))

                FeePayment.objects.create(
                    student=txn.student,
                    amount_paid=txn.amount,
                    balance=Decimal('0.00'),
                    payment_method='mpesa',
                    transaction_ref=txn.mpesa_receipt_number,
                    term='term1',
                    academic_year='',
                    status='completed',
                )
            else:
                txn.status = 'failed' if result_code != 1032 else 'cancelled'

            txn.save()
        except Exception as exc:
            logger.exception('Error processing M-Pesa callback: %s', exc)

        return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})


class StkQueryView(APIView):
    permission_classes = [IsAccountantOrAdmin]

    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'checkout_request_id': {'type': 'string'}}}},
        responses={200: OpenApiResponse(description='STK query result')},
    )
    def post(self, request):
        checkout_request_id = request.data.get('checkout_request_id')
        if not checkout_request_id:
            return Response({'detail': 'checkout_request_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        from .mpesa import MpesaService
        mpesa = MpesaService()
        try:
            result = mpesa.stk_push_query(checkout_request_id)
        except Exception as exc:
            logger.error('STK query error: %s', exc)
            return Response({'detail': 'Query failed.'}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(result)


class MpesaTransactionListView(generics.ListAPIView):
    serializer_class = MpesaTransactionSerializer
    permission_classes = [IsAccountantOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'student']
    search_fields = ['phone_number', 'mpesa_receipt_number', 'account_reference']
    ordering = ['-created_at']
    queryset = MpesaTransaction.objects.select_related('student').all()


class StudentFeeBalanceView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    @extend_schema(responses={200: OpenApiResponse(description='Student fee balance')})
    def get(self, request, student_id):
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

        term = request.query_params.get('term')
        academic_year = request.query_params.get('academic_year')

        structure_qs = FeeStructure.objects.filter(grade_level=student.grade_level)
        payment_qs = FeePayment.objects.filter(student=student, status='completed')

        if term:
            structure_qs = structure_qs.filter(term=term)
            payment_qs = payment_qs.filter(term=term)
        if academic_year:
            structure_qs = structure_qs.filter(academic_year=academic_year)
            payment_qs = payment_qs.filter(academic_year=academic_year)

        total_expected = structure_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_paid = payment_qs.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

        return Response({
            'student_id': student.id,
            'admission_number': student.admission_number,
            'student_name': student.full_name,
            'term': term or 'all',
            'academic_year': academic_year or 'all',
            'total_expected': total_expected,
            'total_paid': total_paid,
            'balance': total_expected - total_paid,
        })
