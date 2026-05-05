from django.urls import path
from .views import (
    ClassroomListCreateView, ClassroomDetailView, ClassroomStudentsView,
    GuardianListCreateView, GuardianDetailView,
    StudentListCreateView, StudentDetailView,
    StudentSearchView, StudentTransferView,
    StudentArchiveView, StudentPromoteAllView,
    StudentBulkImportView, StudentImportTemplateView,
)

urlpatterns = [
    path('classrooms/', ClassroomListCreateView.as_view(), name='classroom-list'),
    path('classrooms/<int:pk>/', ClassroomDetailView.as_view(), name='classroom-detail'),
    path('classrooms/<int:pk>/students/', ClassroomStudentsView.as_view(), name='classroom-students'),
    path('guardians/', GuardianListCreateView.as_view(), name='guardian-list'),
    path('guardians/<int:pk>/', GuardianDetailView.as_view(), name='guardian-detail'),
    path('', StudentListCreateView.as_view(), name='student-list'),
    path('search/', StudentSearchView.as_view(), name='student-search'),
    path('promote-all/', StudentPromoteAllView.as_view(), name='student-promote-all'),
    path('bulk-import/', StudentBulkImportView.as_view(), name='student-bulk-import'),
    path('import-template/', StudentImportTemplateView.as_view(), name='student-import-template'),
    path('<int:pk>/', StudentDetailView.as_view(), name='student-detail'),
    path('<int:pk>/transfer/', StudentTransferView.as_view(), name='student-transfer'),
    path('<int:pk>/archive/', StudentArchiveView.as_view(), name='student-archive'),
]
