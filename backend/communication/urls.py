from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SMSLogViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r'sms-logs', SMSLogViewSet)
router.register(r'notifications', NotificationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
