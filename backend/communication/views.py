from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from academics.permissions import IsAdminUser, IsTeacherOrAdmin
from academics.views.mixins import TenantScopedMixin
from students.models import Classroom

from .models import Announcement, InAppNotification, MessageLog, MessageTemplate, Notification, PushSubscription, SMSLog
from .serializers import (
    AnnouncementSerializer,
    InAppNotificationSerializer,
    MessageLogSerializer,
    MessageTemplateSerializer,
    NotificationSerializer,
    PushSubscriptionSerializer,
    SMSLogSerializer,
)
from .tasks import calculate_next_run

# Channels a teacher is allowed to send on. Admins/superadmins are not
# restricted. SMS is excluded because it carries a direct per-message cost
# via Africa's Talking, and Email is excluded to keep teacher-initiated
# comms inside channels the school can audit/cap easily (in-app + WhatsApp).
# NOTE: there is currently no dedicated "class_teacher" role on CustomUser
# (per Javan: homeroom/class_teacher wiring is planned for a later pass).
# This scoping is written against Classroom.class_teacher directly so it
# keeps working once that role/relationship is fleshed out further — no
# rework needed here.
TEACHER_ALLOWED_CHANNELS = {'inapp', 'whatsapp'}


def _teacher_homeroom_classroom_ids(user):
    """Classrooms where this user is the homeroom (class_teacher)."""
    return set(Classroom.objects.filter(tenant=user.tenant, class_teacher=user).values_list('id', flat=True))


class MessageTemplateViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'channel', 'is_active']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsTeacherOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='preview')
    def preview(self, request, pk=None):
        template = self.get_object()
        vars_ = request.data.get('template_vars', {})
        return Response({'subject': template.render_subject(vars_), 'body': template.render(vars_)})


class AnnouncementViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Announcement.objects.select_related('template', 'recipient_class', 'recipient_user', 'sent_by').all()
    serializer_class = AnnouncementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'recipient_type', 'is_recurring']
    search_fields = ['title', 'body']
    throttle_scope = 'sms_send'

    def get_throttles(self):
        if self.action == 'send':
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_permissions(self):
        return [IsTeacherOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == 'teacher':
            # Teachers only see announcements they themselves created/sent —
            # not the school-wide list. Admins/superadmins see everything
            # in the tenant (already enforced by TenantScopedMixin).
            qs = qs.filter(sent_by=user)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        recipient_type = serializer.validated_data.get('recipient_type')
        recipient_class = serializer.validated_data.get('recipient_class')
        channels = serializer.validated_data.get('channels') or []

        if user.role == 'teacher':
            if recipient_type not in ['class', 'individual']:
                raise ValidationError('Teachers can only send to their own class or individuals.')
            if recipient_type == 'class':
                if not recipient_class or recipient_class.id not in _teacher_homeroom_classroom_ids(user):
                    raise PermissionDenied('You can only send to a class where you are the homeroom (class) teacher.')

            disallowed = sorted(set(channels) - TEACHER_ALLOWED_CHANNELS)
            if disallowed:
                raise ValidationError({
                    'channels': (
                        f'Teachers can only send via {", ".join(sorted(TEACHER_ALLOWED_CHANNELS))}. '
                        f'Not allowed: {", ".join(disallowed)}.'
                    )
                })

        # perform_create runs after sent_by would normally be set on send();
        # we stamp it at creation time too so a teacher's own drafts are
        # immediately visible in their own scoped queryset above.
        serializer.save(tenant=user.tenant, sent_by=user if user.role == 'teacher' else None)

    @action(detail=True, methods=['post'], url_path='send')
    def send(self, request, pk=None):
        announcement = self.get_object()
        if announcement.status in ['sending', 'sent']:
            return Response({'detail': 'Already sent.'}, status=status.HTTP_400_BAD_REQUEST)
        if announcement.send_immediately:
            announcement.status = 'scheduled'
            announcement.sent_by = request.user
            announcement.save(update_fields=['status', 'sent_by'])
            from .tasks import dispatch_announcement_task

            dispatch_announcement_task.delay(str(announcement.id), request.user.tenant_id, request.user.id)
            return Response({'detail': 'Announcement queued for sending.', 'announcement_id': announcement.id})
        if announcement.is_recurring:
            next_run = calculate_next_run(announcement.recurrence_rule, announcement.scheduled_at or timezone.now())
            announcement.status = 'scheduled'
            announcement.sent_by = request.user
            announcement.next_run_at = next_run
            announcement.save(update_fields=['status', 'sent_by', 'next_run_at'])
            return Response({'detail': 'Recurring announcement scheduled.', 'next_run_at': next_run})
        announcement.status = 'scheduled'
        announcement.sent_by = request.user
        announcement.save(update_fields=['status', 'sent_by'])
        return Response({'detail': f'Announcement scheduled for {announcement.scheduled_at}.'})

    @action(detail=True, methods=['post'], url_path='cancel', permission_classes=[IsAdminUser])
    def cancel(self, request, pk=None):
        announcement = self.get_object()
        if announcement.status == 'sent':
            return Response({'detail': 'Cannot cancel sent message.'}, status=status.HTTP_400_BAD_REQUEST)
        announcement.status = 'cancelled'
        announcement.save(update_fields=['status'])
        return Response({'detail': 'Cancelled.'})


class MessageLogViewSet(TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = MessageLog.objects.select_related('announcement', 'recipient_user').all()
    serializer_class = MessageLogSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['channel', 'status', 'announcement']
    search_fields = ['recipient_name', 'recipient_phone', 'recipient_email']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == 'teacher':
            qs = qs.filter(announcement__sent_by=user)
        elif user.role in ('parent', 'guardian'):
            qs = qs.filter(recipient_user=user)
        return qs

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        qs = self.get_queryset()
        return Response({
            'total_messages': qs.count(),
            'by_channel': list(qs.values('channel').annotate(count=Count('id'))),
            'by_status': list(qs.values('status').annotate(count=Count('id'))),
        })


class InAppNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InAppNotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_read', 'type']

    def get_queryset(self):
        return InAppNotification.objects.filter(tenant=self.request.user.tenant, user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        ids = request.data.get('ids', [])
        updated = self.get_queryset().filter(id__in=ids, is_read=False).update(is_read=True, read_at=timezone.now())
        return Response({'updated': updated})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True, read_at=timezone.now())
        return Response({'updated': updated})

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        return Response({'count': self.get_queryset().filter(is_read=False).count()})


class PushSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        sub, created = PushSubscription.objects.update_or_create(
            tenant=request.user.tenant,
            user=request.user,
            endpoint=data['endpoint'],
            defaults={'p256dh': data['p256dh'], 'auth': data['auth'], 'user_agent': data.get('user_agent', ''), 'is_active': True},
        )
        return Response({'subscribed': True, 'created': created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request):
        endpoint = request.data.get('endpoint')
        if not endpoint:
            return Response({'error': 'endpoint required'}, status=status.HTTP_400_BAD_REQUEST)
        PushSubscription.objects.filter(tenant=request.user.tenant, user=request.user, endpoint=endpoint).update(is_active=False)
        return Response({'unsubscribed': True})


class SMSLogViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = SMSLog.objects.all()
    serializer_class = SMSLogSerializer


class NotificationViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer