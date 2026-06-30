from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings
from django.db import models
from django.utils import timezone
from tenants.models import Tenant


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        SUPERADMIN = 'superadmin', 'Super Admin'
        ADMIN = 'admin', 'School Admin'
        TEACHER = 'teacher', 'Teacher'
        BURSAR = 'bursar', 'Bursar'
        PARENT = 'parent', 'Parent / Guardian'
        SUPPORT_STAFF = 'support_staff', 'Support Staff'
        STUDENT = 'student', 'Student'
        GUARDIAN = 'guardian', 'Guardian'
        FINANCE = 'finance', 'Finance Officer'

    ROLE_CHOICES = Role.choices

    email = models.EmailField(unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    is_email_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    objects = CustomUserManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    @property
    def is_support_staff(self):
        return self.role == self.Role.SUPPORT_STAFF


class StaffProfile(models.Model):
    class JobTitle(models.TextChoices):
        TEACHER = 'teacher', 'Teacher'
        BURSAR = 'bursar', 'Bursar'
        COOK = 'cook', 'Cook'
        CLEANER = 'cleaner', 'Cleaner'
        SECURITY = 'security', 'Security Guard'
        DRIVER = 'driver', 'Driver'
        LIBRARIAN = 'librarian', 'Librarian'
        ACCOUNTANT = 'accountant', 'Accountant'
        NURSE = 'nurse', 'Nurse / Matron'
        GROUNDSKEEPER = 'groundskeeper', 'Groundskeeper'
        OTHER = 'other', 'Other'

    class Department(models.TextChoices):
        TEACHING = 'teaching', 'Teaching'
        ADMINISTRATION = 'administration', 'Administration'
        SUPPORT = 'support', 'Support Staff'

    class EmploymentStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ON_LEAVE = 'on_leave', 'On Leave'
        SUSPENDED = 'suspended', 'Suspended'
        TERMINATED = 'terminated', 'Terminated'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_profile',
    )
    employee_number = models.CharField(max_length=30)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    photo = models.ImageField(upload_to='staff_photos/', blank=True, null=True)
    job_title = models.CharField(max_length=20, choices=JobTitle.choices)
    department = models.CharField(max_length=20, choices=Department.choices)
    id_number = models.CharField(max_length=20, blank=True)
    qualifications = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    employment_status = models.CharField(
        max_length=15,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE,
    )
    subjects_qualified = models.ManyToManyField(
        'academics.Subject',
        blank=True,
        related_name='qualified_staff',
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='staff_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['tenant', 'employee_number']
        ordering = ['department', 'last_name']

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def save(self, *args, **kwargs):
        if not self.employee_number:
            year = timezone.now().year
            last = StaffProfile.objects.filter(
                tenant=self.tenant,
                employee_number__startswith=f'EMP/{year}/',
            ).order_by('-employee_number').first()
            seq = 1
            if last:
                try:
                    seq = int(last.employee_number.split('/')[-1]) + 1
                except (ValueError, IndexError):
                    pass
            self.employee_number = f'EMP/{year}/{seq:04d}'

        if self.job_title == self.JobTitle.TEACHER:
            self.department = self.Department.TEACHING
        elif self.job_title in (self.JobTitle.BURSAR, self.JobTitle.ACCOUNTANT):
            self.department = self.Department.ADMINISTRATION
        else:
            self.department = self.Department.SUPPORT
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.employee_number} - {self.get_full_name()} ({self.get_job_title_display()})'


class StaffInvite(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    staff_profile = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='invites')
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=[
            ('teacher', 'Teacher'),
            ('bursar', 'Bursar'),
            ('admin', 'Admin'),
            ('support_staff', 'Support Staff'),
        ],
    )
    token = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invites_sent',
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ['-invited_at']

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.status == self.Status.PENDING and timezone.now() > self.expires_at
