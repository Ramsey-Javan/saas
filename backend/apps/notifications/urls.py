from django.urls import path
from .views import (
    SMSLogListView,
    SMSLogDetailView,
    SendSMSView,
    BulkSMSView,
)

app_name = 'notifications'

urlpatterns = [
    path('sms/logs/', SMSLogListView.as_view(), name='sms-log-list'),
    path('sms/logs/<int:pk>/', SMSLogDetailView.as_view(), name='sms-log-detail'),
    path('sms/send/', SendSMSView.as_view(), name='sms-send'),
    path('sms/bulk/', BulkSMSView.as_view(), name='sms-bulk'),
]
