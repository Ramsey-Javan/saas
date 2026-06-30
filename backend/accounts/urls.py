from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    AcceptInviteView,
    CustomTokenObtainPairView,
    InviteCheckView,
    SchoolProfileView,
    StaffInviteViewSet,
    StaffProfileViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'staff', StaffProfileViewSet, basename='staff')
router.register(r'staff-invites', StaffInviteViewSet, basename='staffinvite')

urlpatterns = [
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('accept-invite/', AcceptInviteView.as_view(), name='accept-invite'),
    path('invite-check/', InviteCheckView.as_view(), name='invite-check'),
    path('school-profile/', SchoolProfileView.as_view(), name='school-profile'),
    path('', include(router.urls)),
]
