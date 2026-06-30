from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlatformSchoolViewSet, PublicSchoolSignupView, SubdomainAvailabilityView, TenantViewSet

router = DefaultRouter()
router.register(r'platform-schools', PlatformSchoolViewSet, basename='platformschool')
router.register(r'', TenantViewSet)

urlpatterns = [
    path('schools/onboard/', PublicSchoolSignupView.as_view(), name='school-onboard'),
    path('schools/check-subdomain/', SubdomainAvailabilityView.as_view(), name='check-subdomain'),
    path('', include(router.urls)),
]
