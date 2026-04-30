from django.contrib import admin
from django_tenants.admin import TenantAdminMixin
from .models import Client, Domain


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 1


@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ['school_name', 'name', 'schema_name', 'subscription_plan', 'is_active', 'created_on']
    list_filter = ['is_active', 'subscription_plan']
    search_fields = ['school_name', 'name', 'schema_name', 'contact_email']
    readonly_fields = ['created_on']
    inlines = [DomainInline]

    fieldsets = (
        ('Tenant Info', {
            'fields': ('name', 'school_name', 'schema_name', 'is_active', 'created_on')
        }),
        ('Subscription', {
            'fields': ('subscription_plan', 'subscription_expires_on')
        }),
        ('Contact', {
            'fields': ('contact_email', 'contact_phone')
        }),
    )


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['domain', 'tenant', 'is_primary']
    list_filter = ['is_primary']
    search_fields = ['domain', 'tenant__school_name']
