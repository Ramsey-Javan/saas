from django.contrib import admin
from .models import SchoolBranding


@admin.register(SchoolBranding)
class SchoolBrandingAdmin(admin.ModelAdmin):
    list_display = ['school_name', 'county', 'school_type', 'curriculum', 'is_active', 'updated_at']
    list_filter = ['school_type', 'curriculum', 'is_active', 'county']
    search_fields = ['school_name', 'county', 'knec_code', 'nemis_code']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('School Identity', {
            'fields': ('school_name', 'logo', 'favicon', 'motto', 'knec_code', 'nemis_code', 'is_active')
        }),
        ('Colors', {
            'fields': ('primary_color', 'secondary_color', 'accent_color')
        }),
        ('Contact & Location', {
            'fields': ('address', 'phone', 'email', 'website', 'county', 'sub_county', 'ward')
        }),
        ('Classification', {
            'fields': ('school_type', 'curriculum', 'established_year')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
