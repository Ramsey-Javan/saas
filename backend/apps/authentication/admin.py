from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'is_active']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone_number']
    ordering = ['last_name', 'first_name']

    fieldsets = UserAdmin.fieldsets + (
        ('School Info', {
            'fields': ('role', 'phone_number', 'profile_picture', 'date_of_birth')
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('School Info', {
            'fields': ('role', 'phone_number', 'first_name', 'last_name', 'email')
        }),
    )
