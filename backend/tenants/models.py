from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Tenant(models.Model):
    """School/Institution model for multi-tenancy."""
    class SchoolType(models.TextChoices):
        PRIMARY = 'primary', _('CBC Primary (PP1-Grade 6)')
        JUNIOR_SECONDARY = 'junior_secondary', _('Junior Secondary (Grade 7-9)')
        SENIOR_SECONDARY = 'senior_secondary', _('Senior Secondary (Grade 10-12)')
        COMBINED = 'combined', _('Combined (Primary + Secondary)')

    class Plan(models.TextChoices):
        TRIAL = 'trial', _('Free Trial')
        STARTER = 'starter', _('Starter (up to 400 students)')
        GROWTH = 'growth', _('Growth (up to 1000 students)')
        ENTERPRISE = 'enterprise', _('Enterprise (Unlimited)')

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    domain = models.URLField(unique=True)
    registration_number = models.CharField(max_length=50, blank=True)
    motto = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    county = models.CharField(max_length=50, blank=True)
    sub_county = models.CharField(max_length=50, blank=True)
    logo = models.ImageField(upload_to='logos/', blank=True)
    primary_color = models.CharField(max_length=7, default='#1a73e8')
    secondary_color = models.CharField(max_length=7, default='#ffffff')
    accent_color = models.CharField(max_length=7, default='#fbbc04')
    school_type = models.CharField(
        max_length=20,
        choices=SchoolType.choices,
        default=SchoolType.COMBINED,
    )
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.TRIAL)
    trial_ends_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Domain(models.Model):
    """Custom domain model for tenant."""
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='custom_domain')
    domain_name = models.CharField(max_length=255, unique=True)
    is_primary = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.domain_name
