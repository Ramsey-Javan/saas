from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CustomTokenObtainPairView,
    LogoutView,
    UserListCreateView,
    UserDetailView,
    CurrentUserView,
    ChangePasswordView,
)

app_name = 'authentication'

urlpatterns = [
    path('token/', CustomTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('users/', UserListCreateView.as_view(), name='user-list-create'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('users/me/', CurrentUserView.as_view(), name='current-user'),
    path('users/me/change-password/', ChangePasswordView.as_view(), name='change-password'),
]
