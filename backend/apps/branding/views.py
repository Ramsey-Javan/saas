from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .models import SchoolBranding
from .serializers import SchoolBrandingSerializer
from apps.authentication.permissions import IsAdminRole


class SchoolBrandingView(APIView):
    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'POST'):
            return [IsAdminRole()]
        return [permissions.AllowAny()]

    @extend_schema(responses=SchoolBrandingSerializer)
    def get(self, request):
        branding = SchoolBranding.objects.filter(is_active=True).first()
        if not branding:
            return Response({'detail': 'No branding configured.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SchoolBrandingSerializer(branding)
        return Response(serializer.data)

    @extend_schema(request=SchoolBrandingSerializer, responses={201: SchoolBrandingSerializer})
    def post(self, request):
        if SchoolBranding.objects.exists():
            return Response(
                {'detail': 'Branding already exists. Use PUT or PATCH to update.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = SchoolBrandingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(request=SchoolBrandingSerializer, responses=SchoolBrandingSerializer)
    def put(self, request):
        return self._update(request, partial=False)

    @extend_schema(request=SchoolBrandingSerializer, responses=SchoolBrandingSerializer)
    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        branding = SchoolBranding.objects.filter(is_active=True).first()
        if not branding:
            return Response({'detail': 'No branding configured.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SchoolBrandingSerializer(branding, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
