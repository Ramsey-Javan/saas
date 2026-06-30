from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from accounts.serializers import PlatformSchoolSerializer
from accounts.models import CustomUser
from students.models import Student
from .models import Tenant, Domain
from .permissions import IsSuperAdmin
from .serializers import TenantSerializer


def serialize_public_tenant(request, school):
    logo_url = request.build_absolute_uri(school.logo.url) if school.logo else None
    return {
        'id': school.id,
        'name': school.name,
        'logo': logo_url,
        'primary_color': school.primary_color,
        'secondary_color': school.secondary_color,
        'accent_color': school.accent_color,
        'motto': school.motto,
    }


DEFAULT_PLATFORM_BRANDING = {
    'name': 'School Management Platform',
    'logo': None,
    'primary_color': '#1e40af',
    'secondary_color': '#ffffff',
    'accent_color': '#fbbc04',
    'motto': '',
}


class PublicTenantInfoView(APIView):
    """
    Public branding info for the current school/domain, used by the
    pre-login screen before any JWT exists.

    Resolution order:
      1. Domain.domain_name exact match against the request host — this is
         the real per-tenant signal in production (e.g. stmarys.app.co.ke).
      2. Tenant.domain (legacy/manual field) as a fallback for tenants that
         haven't been given a Domain row yet.
      3. Platform-default branding (NOT "first tenant created") if nothing
         matches — this is the deliberate fix: on bare `localhost` there is
         no way to know which tenant is meant pre-login, so we no longer
         guess by picking an arbitrary tenant. Each school's branding will
         correctly resolve once dev/staging assigns per-tenant subdomains
         or hostnames (e.g. alpha.localhost, demo.localhost via /etc/hosts).
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        host = request.get_host().split(':')[0]

        domain_row = Domain.objects.filter(domain_name__iexact=host).select_related('tenant').first()
        if domain_row:
            return Response(serialize_public_tenant(request, domain_row.tenant))

        scheme_host = f'{request.scheme}://{host}'
        school = (
            Tenant.objects.filter(domain__iexact=scheme_host).first()
            or Tenant.objects.filter(domain__icontains=host).first()
        )
        if school:
            return Response(serialize_public_tenant(request, school))

        return Response(DEFAULT_PLATFORM_BRANDING)


class TenantViewSet(viewsets.ModelViewSet):
    """ViewSet for Tenant management."""
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer


class PlatformSchoolViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = PlatformSchoolSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['plan', 'is_active', 'school_type']
    search_fields = ['name', 'email', 'slug', 'domain']

    def create(self, request):
        """Superadmin creates a school and its admin user."""
        required = ['name', 'slug', 'admin_email', 'admin_password']
        missing = [f for f in required if not request.data.get(f)]
        if missing:
            return Response(
                {'error': f'Missing required fields: {", ".join(missing)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = request.data['name']
        slug = slugify(request.data['slug'])
        admin_email = request.data['admin_email']
        admin_password = request.data['admin_password']

        if Tenant.objects.filter(slug=slug).exists():
            return Response(
                {'error': 'A school with this slug already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if CustomUser.objects.filter(email=admin_email).exists():
            return Response(
                {'error': 'An account with this admin email already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            school = Tenant.objects.create(
                name=name,
                slug=slug,
                domain=request.data.get('domain') or f'https://{slug}.yourapp.co.ke',
                email=request.data.get('email', ''),
                phone=request.data.get('phone', ''),
                school_type=request.data.get('school_type', Tenant.SchoolType.COMBINED),
                plan=Tenant.Plan.TRIAL,
                trial_ends_on=timezone.localdate() + timedelta(days=14),
            )
            admin = CustomUser.objects.create_user(
                email=admin_email,
                password=admin_password,
                username=admin_email,
                first_name=request.data.get('admin_first_name', 'School'),
                last_name=request.data.get('admin_last_name', 'Admin'),
                role=CustomUser.Role.ADMIN,
                tenant=school,
                is_email_verified=True,
            )

        return Response(
            {
                **PlatformSchoolSerializer(school, context={'request': request}).data,
                'admin_email': admin.email,
                'admin_password': admin_password,  # superadmin sees this once
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['patch'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        school = self.get_object()
        school.is_active = not school.is_active
        school.save(update_fields=['is_active'])
        return Response(self.get_serializer(school).data)

    @action(detail=True, methods=['patch'], url_path='change-plan')
    def change_plan(self, request, pk=None):
        school = self.get_object()
        new_plan = request.data.get('plan')
        if new_plan not in dict(Tenant.Plan.choices):
            return Response({'error': 'Invalid plan.'}, status=status.HTTP_400_BAD_REQUEST)
        school.plan = new_plan
        if new_plan != Tenant.Plan.TRIAL:
            school.trial_ends_on = None
        school.save(update_fields=['plan', 'trial_ends_on'])
        return Response(self.get_serializer(school).data)

    @action(detail=True, methods=['post'], url_path='seed-demo-data')
    def seed_demo_data(self, request, pk=None):
        school = self.get_object()
        return Response({'message': f'Demo data seeding is not configured for {school.name}.'})

    @action(detail=False, methods=['get'], url_path='stats')
    def platform_stats(self, request):
        schools = Tenant.objects.all()
        return Response({
            'total_schools': schools.count(),
            'active_schools': schools.filter(is_active=True).count(),
            'trial_schools': schools.filter(plan=Tenant.Plan.TRIAL).count(),
            'paying_schools': schools.exclude(plan=Tenant.Plan.TRIAL).count(),
            'total_students_platform_wide': Student.objects.filter(
                tenant__in=schools.filter(is_active=True),
                is_active=True,
            ).count(),
        })


class PublicSchoolSignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        required = ['name', 'subdomain', 'email', 'phone', 'school_type', 'admin_email', 'admin_password']
        missing = [field for field in required if not request.data.get(field)]
        if missing:
            return Response({'error': f'Missing required fields: {", ".join(missing)}'}, status=status.HTTP_400_BAD_REQUEST)

        subdomain = slugify(request.data['subdomain'])
        if not subdomain:
            return Response({'error': 'Enter a valid subdomain.'}, status=status.HTTP_400_BAD_REQUEST)
        if Tenant.objects.filter(slug=subdomain).exists():
            return Response({'error': 'This subdomain is already taken.'}, status=status.HTTP_400_BAD_REQUEST)
        if CustomUser.objects.filter(email=request.data['admin_email']).exists():
            return Response({'error': 'An account with this admin email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            school = Tenant.objects.create(
                name=request.data['name'],
                slug=subdomain,
                domain=f'https://{subdomain}.yourapp.co.ke',
                email=request.data['email'],
                phone=request.data['phone'],
                school_type=request.data['school_type'],
                plan=Tenant.Plan.TRIAL,
                trial_ends_on=timezone.localdate() + timedelta(days=14),
            )
            CustomUser.objects.create_user(
                email=request.data['admin_email'],
                password=request.data['admin_password'],
                username=request.data['admin_email'],
                role=CustomUser.Role.ADMIN,
                tenant=school,
                is_email_verified=True,
            )

        return Response({
            'id': school.id,
            'name': school.name,
            'subdomain': subdomain,
            'login_url': school.domain,
        }, status=status.HTTP_201_CREATED)


class SubdomainAvailabilityView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        subdomain = slugify(request.query_params.get('subdomain', ''))
        if not subdomain:
            return Response({'available': False, 'error': 'Enter a valid subdomain.'})
        return Response({'available': not Tenant.objects.filter(slug=subdomain).exists(), 'subdomain': subdomain})