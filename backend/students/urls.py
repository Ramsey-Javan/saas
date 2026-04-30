from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StudentViewSet, GuardianViewSet, AdmissionViewSet

router = DefaultRouter()
router.register(r'students', StudentViewSet)
router.register(r'guardians', GuardianViewSet)
router.register(r'admissions', AdmissionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
