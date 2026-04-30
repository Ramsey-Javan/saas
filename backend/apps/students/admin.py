from django.contrib import admin
from .models import Student, Admission


class AdmissionInline(admin.TabularInline):
    model = Admission
    extra = 0
    readonly_fields = ['created_at']
    fields = ['academic_year', 'date_admitted', 'admission_type', 'grade_on_admission', 'status', 'created_at']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        'admission_number', 'last_name', 'first_name', 'grade_level',
        'stream', 'gender', 'parent_phone', 'is_active',
    ]
    list_filter = ['grade_level', 'gender', 'stream', 'is_active']
    search_fields = ['first_name', 'last_name', 'admission_number', 'parent_phone', 'parent_name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [AdmissionInline]

    fieldsets = (
        ('Student Info', {
            'fields': (
                'first_name', 'last_name', 'other_names', 'admission_number',
                'date_of_birth', 'gender', 'photo', 'is_active',
            )
        }),
        ('Academic Info', {
            'fields': ('grade_level', 'stream')
        }),
        ('Parent/Guardian', {
            'fields': (
                'parent_name', 'parent_phone', 'parent_email', 'parent_relationship',
                'parent_occupation', 'parent_address',
                'secondary_contact_name', 'secondary_contact_phone',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ['student', 'academic_year', 'date_admitted', 'admission_type', 'status']
    list_filter = ['academic_year', 'admission_type', 'status']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']
    readonly_fields = ['created_at']
    autocomplete_fields = ['student']
