from rest_framework import serializers
from .models import Class, Subject, CBCGrade, Attendance


class ClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = Class
        fields = '__all__'


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = '__all__'


class CBCGradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CBCGrade
        fields = '__all__'


class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = '__all__'
