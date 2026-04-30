from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.contrib.auth import get_user_model
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserDetailSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
)
from .permissions import IsAdminRole

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'refresh': {'type': 'string'}}}},
        responses={200: OpenApiResponse(description='Logged out successfully')},
    )
    def post(self, request):
        try:
            refresh_token = request.data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


class UserListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return User.objects.filter(is_superuser=False)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer
        return UserDetailSerializer


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = UserDetailSerializer
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UserUpdateSerializer
        return UserDetailSerializer


class CurrentUserView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UserUpdateSerializer
        return UserDetailSerializer


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ChangePasswordSerializer, responses={200: OpenApiResponse(description='Password changed')})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            request.user.set_password(serializer.validated_data['new_password'])
            request.user.save(update_fields=['password'])
            return Response({'detail': 'Password changed successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
