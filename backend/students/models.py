from datetime import date

from django.contrib.auth import get_user_model
from django.db import models
from tenants.models import Tenant

User = get_user_model()


class Classroom(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    grade_level = models.CharField(max_length=50)
    stream = models.CharField(max_length=10, blank=True)
    class_teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='classrooms',
    )
    academic_year = models.CharField(max_length=20)
    capacity = models.IntegerField(default=40)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('tenant', 'name', 'stream', 'academic_year')

    def __str__(self):
        return f"{self.name} {self.stream}".strip()

    @property
    def student_count(self):
        return self.students.filter(is_active=True).count()


class Student(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        TRANSFERRED = 'transferred', 'Transferred'
        GRADUATED = 'graduated', 'Graduated'
        DROPPED = 'dropped', 'Dropped'

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student',
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=150)
    middle_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150)
    admission_number = models.CharField(max_length=50, unique=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female')])
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
    )
    primary_guardian = models.ForeignKey(
        'Guardian',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    admission_date = models.DateField(auto_now_add=True)
    birth_certificate_no = models.CharField(max_length=100, blank=True)
    nemis_no = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to='students/', blank=True, null=True)
    blood_group = models.CharField(max_length=5, blank=True)
    medical_notes = models.TextField(blank=True)
    special_needs = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenant', 'admission_number')

    def __str__(self):
        return f"{self.get_full_name()} - {self.admission_number}"

    def get_full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(part for part in parts if part).strip()

    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class Guardian(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guardian_profile',
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15)
    alt_phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    relationship = models.CharField(max_length=50)
    national_id = models.CharField(max_length=50, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=True)

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def name(self):
        return self.full_name

    @property
    def phone_number(self):
        return self.phone


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
