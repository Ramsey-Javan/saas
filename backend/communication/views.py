from rest_framework import viewsets
from .models import SMSLog, Notification
from .serializers import SMSLogSerializer, NotificationSerializer


class SMSLogViewSet(viewsets.ModelViewSet):
    queryset = SMSLog.objects.all()
    serializer_class = SMSLogSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
