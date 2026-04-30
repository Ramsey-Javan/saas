from django.db import models
from django.contrib.auth import get_user_model
from tenants.models import Tenant

User = get_user_model()


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    admission_number = models.CharField(max_length=50, unique=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female')])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenant', 'admission_number')

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.admission_number}"


class Guardian(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='guardians')
    name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    is_primary = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.student.admission_number}"


class Admission(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='admission')
    admission_date = models.DateField(auto_now_add=True)
    class_admitted = models.CharField(max_length=50)
    previous_school = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('inactive', 'Inactive')],
        default='active'
    )

    def __str__(self):
        return f"Admission - {self.student.admission_number}"
