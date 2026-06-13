from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnouncementViewSet,
    InAppNotificationViewSet,
    MessageLogViewSet,
    MessageTemplateViewSet,
    NotificationViewSet,
    PushSubscriptionView,
    SMSLogViewSet,
)

router = DefaultRouter()
router.register('templates', MessageTemplateViewSet, basename='template')
router.register('announcements', AnnouncementViewSet, basename='announcement')
router.register('logs', MessageLogViewSet, basename='log')
router.register('notifications', InAppNotificationViewSet, basename='notification')
router.register('sms-logs', SMSLogViewSet, basename='sms-log')
router.register('legacy-notifications', NotificationViewSet, basename='legacy-notification')

urlpatterns = [
    path('', include(router.urls)),
    path('push/subscribe/', PushSubscriptionView.as_view(), name='push-subscribe'),
    path('push/unsubscribe/', PushSubscriptionView.as_view(), name='push-unsubscribe'),
]
