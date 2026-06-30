from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, filters, viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from academics.views.mixins import TenantScopedMixin
from .models import CustomUser, StaffInvite, StaffProfile
from .serializers import (
    AcceptInviteSerializer,
    CreateStaffSerializer,
    CustomTokenObtainPairSerializer,
    DeactivateStaffSerializer,
    SchoolProfileSerializer,
    StaffInviteSerializer,
    StaffProfileSerializer,
    UpdateStaffSerializer,
    UserSerializer,
)
from .permissions import IsSchoolAdmin, IsTeacher, IsBursar, IsParent


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User management."""
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'superadmin':
            return CustomUser.objects.all()
        if user.tenant:
            return CustomUser.objects.filter(tenant=user.tenant)
        return CustomUser.objects.none()

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class StaffProfileViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    queryset = StaffProfile.objects.select_related('user').prefetch_related('subjects_qualified').all()
    serializer_class = StaffProfileSerializer
    permission_classes = [IsSchoolAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['job_title', 'department', 'employment_status', 'is_active']
    search_fields = ['first_name', 'last_name', 'employee_number', 'phone', 'id_number']
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='onboard')
    def onboard(self, request):
        serializer = CreateStaffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant = request.user.tenant
        if not tenant:
            return Response(
                {'error': 'Platform superadmins cannot onboard staff directly. Please log in as a school admin.'},
                status=status.HTTP_403_FORBIDDEN
            )

        with transaction.atomic():
            profile = StaffProfile.objects.create(
                tenant=tenant,
                first_name=data['first_name'],
                last_name=data['last_name'],
                phone=data['phone'],
                email=data.get('email', ''),
                job_title=data['job_title'],
                id_number=data.get('id_number', ''),
                qualifications=data.get('qualifications', ''),
                start_date=data['start_date'],
                created_by=request.user,
            )

            subject_ids = data.get('subjects_qualified', [])
            if subject_ids:
                profile.subjects_qualified.set(subject_ids)

            method = data['onboarding_method']
            if method == 'direct':
                email = data.get('email') or f"{profile.employee_number.lower().replace('/', '-')}@staff.local"
                new_user = CustomUser.objects.create_user(
                    email=email,
                    password=data['temp_password'],
                    username=email,
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                    phone_number=data['phone'],
                    role=data['role'],
                    tenant=tenant,
                )
                profile.user = new_user
                profile.email = email
                profile.save(update_fields=['user', 'email', 'updated_at'])

                return Response({
                    'staff': StaffProfileSerializer(profile).data,
                    'login_email': new_user.email,
                    'message': 'Staff account created. Share the temporary password with them directly.',
                }, status=status.HTTP_201_CREATED)

            if method == 'invite':
                invite = StaffInvite.objects.create(
                    tenant=tenant,
                    staff_profile=profile,
                    email=data['email'],
                    role=data['role'],
                    invited_by=request.user,
                )
                self._send_invite_email(request, invite)
                return Response({
                    'staff': StaffProfileSerializer(profile).data,
                    'invite': StaffInviteSerializer(invite).data,
                    'message': f'Invite email sent to {invite.email}.',
                }, status=status.HTTP_201_CREATED)

            return Response({
                'staff': StaffProfileSerializer(profile).data,
                'message': 'Staff profile created without login access.',
            }, status=status.HTTP_201_CREATED)

    def _send_invite_email(self, request, invite):
        from communication.services import EmailService

        origin = request.build_absolute_uri('/').rstrip('/')
        invite_url = f'{origin}/accept-invite?token={invite.token}'
        EmailService().send(
            [invite.email],
            subject=f'Invitation to join {invite.tenant.name}',
            body=(
                f"You've been invited to join {invite.tenant.name} as "
                f"{invite.get_role_display()}.\n\n"
                f"Set up your account here: {invite_url}\n\n"
                f"This link expires in 7 days."
            ),
        )

    @action(detail=True, methods=['get'], url_path='assignments')
    def assignments(self, request, pk=None):
        from .utils import get_active_assignments

        profile = self.get_object()
        if not profile.user:
            return Response({
                'class_subject_assignments': [],
                'class_teacher_roles': [],
                'exam_subjects': [],
                'total_count': 0,
            })

        data = get_active_assignments(profile.user, request.user.tenant)
        return Response({
            'class_subject_assignments': [
                {'id': item.id, 'classroom': str(item.classroom), 'subject': item.subject.name}
                for item in data['class_subject_assignments']
            ],
            'class_teacher_roles': [
                {'id': item.id, 'classroom': str(item)}
                for item in data['class_teacher_roles']
            ],
            'exam_subjects': [
                {'id': item.id, 'exam': item.exam.name, 'subject': item.subject.name}
                for item in data['exam_subjects']
            ],
            'total_count': data['total_count'],
        })

    @action(detail=True, methods=['post'], url_path='send-invite')
    def send_invite(self, request, pk=None):
        profile = self.get_object()
        if profile.user:
            return Response(
                {'error': 'This staff member already has login access.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = request.data.get('email') or profile.email
        role = request.data.get('role')
        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not role:
            return Response({'error': 'Role is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if StaffInvite.objects.filter(
            staff_profile=profile,
            status=StaffInvite.Status.PENDING,
        ).exists():
            return Response(
                {'error': 'A pending invite already exists for this staff member.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invite = StaffInvite.objects.create(
            tenant=request.user.tenant,
            staff_profile=profile,
            email=email,
            role=role,
            invited_by=request.user,
        )
        profile.email = email
        profile.save(update_fields=['email', 'updated_at'])
        self._send_invite_email(request, invite)
        return Response({
            'invite': StaffInviteSerializer(invite).data,
            'message': f'Invite email sent to {invite.email}.',
        })

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return UpdateStaffSerializer
        return self.serializer_class

    def _class_teacher_warning(self, profile):
        """
        If this staff member is currently homeroom teacher for any
        classroom, return a warning string. Used when job_title or role
        is being changed away from 'teacher' so the admin isn't surprised
        by a stale Classroom.class_teacher FK pointing at a non-teacher.
        Non-blocking by design (per Javan: warn, don't block).
        """
        if not profile.user:
            return None
        from students.models import Classroom

        classrooms = Classroom.objects.filter(tenant=profile.tenant, class_teacher=profile.user)
        if not classrooms.exists():
            return None
        names = ', '.join(str(c) for c in classrooms)
        return (
            f'{profile.get_full_name()} is still set as class teacher for: {names}. '
            f'You may want to reassign these classes from their staff profile.'
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        was_teacher = instance.job_title == StaffProfile.JobTitle.TEACHER

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance.refresh_from_db()

        warning = None
        if was_teacher and instance.job_title != StaffProfile.JobTitle.TEACHER:
            warning = self._class_teacher_warning(instance)

        data = StaffProfileSerializer(instance).data
        if warning:
            data['warning'] = warning
        return Response(data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='change-role')
    def change_role(self, request, pk=None):
        """
        Change the role of this staff member's linked CustomUser login.
        Separate from the regular update() above because it touches a
        different model and needs safety checks that don't apply to any
        other field on this form.
        """
        profile = self.get_object()
        if not profile.user:
            return Response(
                {'error': 'This staff member has no login account yet, so there is no role to change.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_role = request.data.get('role')
        valid_roles = dict(CustomUser.Role.choices)
        if new_role not in valid_roles:
            return Response({'error': 'Invalid role.'}, status=status.HTTP_400_BAD_REQUEST)

        target_user = profile.user

        if target_user.id == request.user.id:
            return Response(
                {'error': 'You cannot change your own role.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        was_admin = target_user.role == CustomUser.Role.ADMIN
        becoming_non_admin = was_admin and new_role != CustomUser.Role.ADMIN
        if becoming_non_admin:
            other_admins = CustomUser.objects.filter(
                tenant=target_user.tenant,
                role=CustomUser.Role.ADMIN,
                is_active=True,
            ).exclude(id=target_user.id)
            if not other_admins.exists():
                return Response(
                    {'error': 'Cannot change this role — they are the only admin for this school.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        was_teacher_role = target_user.role == CustomUser.Role.TEACHER
        target_user.role = new_role
        target_user.save(update_fields=['role'])

        warning = None
        if was_teacher_role and new_role != CustomUser.Role.TEACHER:
            warning = self._class_teacher_warning(profile)

        response_data = {
            'detail': f'Role updated to {valid_roles[new_role]}.',
            'staff': StaffProfileSerializer(profile).data,
        }
        if warning:
            response_data['warning'] = warning
        return Response(response_data)
    
    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        from .utils import deactivate_and_reassign

        profile = self.get_object()
        serializer = DeactivateStaffSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        reassign_to = serializer.validated_data.get('reassign_to')
        if reassign_to and reassign_to.tenant_id != request.user.tenant_id:
            return Response({'error': 'Reassignment teacher is not in this school.'}, status=status.HTTP_400_BAD_REQUEST)

        if not profile.user:
            profile.employment_status = StaffProfile.EmploymentStatus.TERMINATED
            profile.end_date = timezone.localdate()
            profile.is_active = False
            profile.save(update_fields=['employment_status', 'end_date', 'is_active', 'updated_at'])
            return Response({'message': 'Staff profile deactivated.', 'reassigned': None})

        reassigned = deactivate_and_reassign(profile.user, request.user.tenant, reassign_to_user=reassign_to)
        return Response({'message': 'Staff member deactivated.', 'reassigned': reassigned})


class StaffInviteViewSet(TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StaffInvite.objects.select_related('staff_profile', 'invited_by').all()
    serializer_class = StaffInviteSerializer
    permission_classes = [IsSchoolAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'staff_profile']

    @action(detail=True, methods=['post'], url_path='resend')
    def resend(self, request, pk=None):
        invite = self.get_object()
        if invite.status != StaffInvite.Status.PENDING:
            return Response({'error': 'Only pending invites can be resent.'}, status=status.HTTP_400_BAD_REQUEST)
        StaffProfileViewSet()._send_invite_email(request, invite)
        return Response({'message': 'Invite resent.'})

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        invite = self.get_object()
        invite.status = StaffInvite.Status.CANCELLED
        invite.save(update_fields=['status'])
        return Response({'message': 'Invite cancelled.'})


class AcceptInviteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = AcceptInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        invite = StaffInvite.objects.filter(
            token=data['token'],
            status=StaffInvite.Status.PENDING,
        ).select_related('staff_profile', 'tenant').first()

        if not invite:
            return Response({'error': 'Invalid or already used invite.'}, status=status.HTTP_404_NOT_FOUND)
        if invite.is_expired:
            invite.status = StaffInvite.Status.EXPIRED
            invite.save(update_fields=['status'])
            return Response({'error': 'This invite has expired. Ask your admin to resend it.'}, status=status.HTTP_400_BAD_REQUEST)

        profile = invite.staff_profile
        with transaction.atomic():
            new_user = CustomUser.objects.create_user(
                email=invite.email,
                password=data['password'],
                username=invite.email,
                first_name=profile.first_name,
                last_name=profile.last_name,
                phone_number=profile.phone,
                role=invite.role,
                tenant=invite.tenant,
            )
            profile.user = new_user
            profile.email = invite.email
            profile.save(update_fields=['user', 'email', 'updated_at'])

            invite.status = StaffInvite.Status.ACCEPTED
            invite.accepted_at = timezone.now()
            invite.save(update_fields=['status', 'accepted_at'])

        return Response({'message': 'Account created successfully. You can now log in.', 'email': new_user.email})


class InviteCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        token = request.query_params.get('token')
        invite = StaffInvite.objects.filter(token=token).select_related('staff_profile').first()
        if not invite:
            return Response({'valid': False, 'error': 'Invalid invite link.'}, status=status.HTTP_404_NOT_FOUND)
        if invite.status != StaffInvite.Status.PENDING or invite.is_expired:
            return Response({'valid': False, 'error': 'This invite is no longer valid.'})
        return Response({
            'valid': True,
            'name': invite.staff_profile.get_full_name(),
            'role': invite.get_role_display(),
            'email': invite.email,
        })


class SchoolProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = SchoolProfileSerializer
    permission_classes = [IsSchoolAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return self.request.user.tenant
