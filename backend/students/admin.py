from django.contrib import admin
from .models import Classroom, Student, Guardian, Admission


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('admission_number', 'get_full_name', 'classroom', 'gender', 'status', 'is_active')
    search_fields = ('admission_number', 'first_name', 'last_name')
    list_filter = ('gender', 'status', 'is_active')

    @admin.display(description='Student')
    def get_full_name(self, obj):
        return obj.get_full_name()


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'relationship', 'is_primary')
    search_fields = ('first_name', 'last_name', 'phone', 'national_id')


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('name', 'grade_level', 'stream', 'academic_year', 'capacity', 'is_active')


@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'admission_date', 'class_admitted', 'status')
