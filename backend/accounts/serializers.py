from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from tenants.models import Tenant
from .models import CustomUser, StaffInvite, StaffProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'role', 'tenant', 'phone_number')


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        tenant = getattr(self.user, 'tenant', None)
        if tenant and not tenant.is_active:
            raise serializers.ValidationError(
                'This school account is no longer active. Please contact support to reactivate.'
            )
        data['user'] = UserSerializer(self.user).data
        # Include full tenant branding for ALL users (not just admins)
        if tenant:
            data['tenant'] = {
                'id': tenant.id,
                'name': tenant.name,
                'slug': tenant.slug,
                'domain': tenant.domain,
                'logo': tenant.logo.url if tenant.logo else None,
                'primary_color': tenant.primary_color,
                'secondary_color': tenant.secondary_color,
                'accent_color': tenant.accent_color,
                'school_type': tenant.school_type,
                'plan': tenant.plan,
                'trial_ends_on': str(tenant.trial_ends_on) if tenant.trial_ends_on else None,
                'is_active': tenant.is_active,
            }
        else:
            data['tenant'] = None
        return data


class StaffProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    has_login = serializers.SerializerMethodField()
    subjects_qualified_names = serializers.SerializerMethodField()

    class Meta:
        model = StaffProfile
        fields = [
            'id', 'employee_number', 'first_name', 'last_name', 'full_name',
            'phone', 'email', 'photo', 'job_title', 'department', 'id_number',
            'qualifications', 'start_date', 'end_date', 'employment_status',
            'subjects_qualified', 'subjects_qualified_names', 'is_active',
            'user', 'user_email', 'user_role', 'has_login', 'created_at',
        ]
        read_only_fields = ['employee_number', 'department', 'created_at']

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None

    def get_user_role(self, obj):
        return obj.user.role if obj.user else None

    def get_has_login(self, obj):
        return obj.user is not None

    def get_subjects_qualified_names(self, obj):
        return [subject.name for subject in obj.subjects_qualified.all()]


class CreateStaffSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True)
    job_title = serializers.ChoiceField(choices=StaffProfile.JobTitle.choices)
    id_number = serializers.CharField(required=False, allow_blank=True)
    qualifications = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateField()
    subjects_qualified = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
    )
    onboarding_method = serializers.ChoiceField(choices=['direct', 'invite', 'none'])
    temp_password = serializers.CharField(required=False, write_only=True)
    role = serializers.ChoiceField(
        choices=[
            ('teacher', 'Teacher'),
            ('bursar', 'Bursar'),
            ('admin', 'Admin'),
            ('support_staff', 'Support Staff'),
        ],
        required=False,
    )

    def validate(self, attrs):
        method = attrs.get('onboarding_method')
        if method == 'direct':
            if not attrs.get('temp_password'):
                raise serializers.ValidationError({'temp_password': 'Required for direct onboarding.'})
            if not attrs.get('role'):
                raise serializers.ValidationError({'role': 'Required for direct onboarding.'})
        if method == 'invite':
            if not attrs.get('email'):
                raise serializers.ValidationError({'email': 'Email is required to send an invite.'})
            if not attrs.get('role'):
                raise serializers.ValidationError({'role': 'Required for invite onboarding.'})
        return attrs


class StaffInviteSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    invited_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StaffInvite
        fields = [
            'id', 'staff_profile', 'staff_name', 'email', 'role', 'invited_by',
            'invited_by_name', 'invited_at', 'expires_at', 'accepted_at', 'status',
        ]
        read_only_fields = ['token', 'invited_by', 'invited_at', 'accepted_at']

    def get_staff_name(self, obj):
        return obj.staff_profile.get_full_name()

    def get_invited_by_name(self, obj):
        return obj.invited_by.get_full_name() if obj.invited_by else None


class AcceptInviteSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)


class DeactivateStaffSerializer(serializers.Serializer):
    reassign_to = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.none(),
        required=False,
        allow_null=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and getattr(request.user, 'tenant_id', None):
            self.fields['reassign_to'].queryset = CustomUser.objects.filter(
                role=CustomUser.Role.TEACHER,
                tenant=request.user.tenant,
                is_active=True,
            )




class UpdateStaffSerializer(serializers.ModelSerializer):
    """
    Edit form for an existing StaffProfile. Deliberately excludes
    employee_number (auto-generated, immutable) and department (derived
    from job_title in StaffProfile.save()). Role changes are handled by
    a separate action (see StaffProfileViewSet.change_role) because they
    touch CustomUser, not StaffProfile, and need extra safety checks.
    """
    class Meta:
        model = StaffProfile
        fields = [
            'first_name', 'last_name', 'phone', 'email', 'id_number',
            'job_title', 'qualifications', 'start_date', 'subjects_qualified',
        ]

    def validate_job_title(self, value):
        # Mirrors AddStaffPage's job title list — kept loose here since
        # the model's own choices already enforce the valid set; this is
        # just where you'd add cross-field rules later if needed.
        return value


class SchoolProfileSerializer(serializers.ModelSerializer):
    is_in_grace_period = serializers.SerializerMethodField()
    days_until_trial_expiry = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'motto', 'email', 'phone', 'address', 'county',
            'sub_county', 'logo', 'primary_color', 'secondary_color',
            'accent_color', 'school_type', 'plan', 'trial_ends_on',
            'is_active', 'is_in_grace_period', 'days_until_trial_expiry',
        ]
        read_only_fields = ['id', 'plan', 'trial_ends_on', 'is_active']

    def get_is_in_grace_period(self, obj):
        return obj.is_in_grace_period()

    def get_days_until_trial_expiry(self, obj):
        return obj.days_until_trial_expiry()


class PlatformSchoolSerializer(serializers.ModelSerializer):
    student_count = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()
    admin_email = serializers.SerializerMethodField()
    admin_name = serializers.SerializerMethodField()
    is_in_grace_period = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'domain', 'email', 'phone', 'school_type',
            'plan', 'trial_ends_on', 'is_active', 'student_count',
            'staff_count', 'admin_email', 'admin_name', 'is_in_grace_period',
            'days_until_expiry', 'created_at',
        ]

    def get_student_count(self, obj):
        from students.models import Student
        return Student.objects.filter(tenant=obj, is_active=True).count()

    def get_staff_count(self, obj):
        return StaffProfile.objects.filter(tenant=obj, is_active=True).count()

    def get_admin_email(self, obj):
        admin = CustomUser.objects.filter(tenant=obj, role='admin').first()
        return admin.email if admin else None

    def get_admin_name(self, obj):
        admin = CustomUser.objects.filter(tenant=obj, role='admin').first()
        return admin.get_full_name() if admin else None

    def get_is_in_grace_period(self, obj):
        return obj.is_in_grace_period()

    def get_days_until_expiry(self, obj):
        return obj.days_until_trial_expiry()