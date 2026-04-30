from django.contrib import admin
from .models import Student, Guardian, Admission


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('admission_number', 'user', 'gender', 'is_active')


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ('name', 'student', 'relationship', 'is_primary')


@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'admission_date', 'class_admitted', 'status')
