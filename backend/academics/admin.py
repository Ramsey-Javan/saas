from django.contrib import admin
from .models import Class, Subject, CBCGrade, Attendance


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'stream', 'tenant', 'class_teacher', 'capacity')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'tenant', 'is_optional')


@admin.register(CBCGrade)
class CBCGradeAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'term', 'year', 'grade')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'status')
