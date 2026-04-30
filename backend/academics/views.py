from rest_framework import viewsets
from .models import Class, Subject, CBCGrade, Attendance
from .serializers import ClassSerializer, SubjectSerializer, CBCGradeSerializer, AttendanceSerializer


class ClassViewSet(viewsets.ModelViewSet):
    queryset = Class.objects.all()
    serializer_class = ClassSerializer


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer


class CBCGradeViewSet(viewsets.ModelViewSet):
    queryset = CBCGrade.objects.all()
    serializer_class = CBCGradeSerializer


class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
