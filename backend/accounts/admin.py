from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, StaffInvite, StaffProfile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Tenant & Role', {'fields': ('tenant', 'role')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_staff')


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('employee_number', 'first_name', 'last_name', 'job_title', 'department', 'employment_status')
    list_filter = ('department', 'job_title', 'employment_status', 'is_active')
    search_fields = ('employee_number', 'first_name', 'last_name', 'phone', 'email')


@admin.register(StaffInvite)
class StaffInviteAdmin(admin.ModelAdmin):
    list_display = ('email', 'staff_profile', 'role', 'status', 'invited_at', 'expires_at')
    list_filter = ('role', 'status')
    search_fields = ('email', 'staff_profile__first_name', 'staff_profile__last_name')
