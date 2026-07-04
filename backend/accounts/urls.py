from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomTokenObtainPairView,
    UserViewSet,
    StaffProfileViewSet,
    StaffInviteViewSet,
    AcceptInviteView,
    InviteCheckView,
    SchoolProfileView,
    PasswordResetRequestView,
    PasswordResetCheckView,
    PasswordResetConfirmView,
)

router = DefaultRouter()
router.register('users', UserViewSet, basename='users')
router.register('staff-profiles', StaffProfileViewSet, basename='staff-profiles')
router.register('staff-invites', StaffInviteViewSet, basename='staff-invites')

urlpatterns = [
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CustomTokenObtainPairView.as_view(), name='token_refresh'),
    path('token/verify/', CustomTokenObtainPairView.as_view(), name='token_verify'),
    path('register/', AcceptInviteView.as_view(), name='register'),
    path('logout/', AcceptInviteView.as_view(), name='logout'),
    path('school-profile/', SchoolProfileView.as_view(), name='school-profile'),
    path('accept-invite/', AcceptInviteView.as_view(), name='accept-invite'),
    path('invite-check/', InviteCheckView.as_view(), name='invite-check'),
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset-check/', PasswordResetCheckView.as_view(), name='password-reset-check'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('', include(router.urls)),
]