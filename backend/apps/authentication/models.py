from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
        ('parent', 'Parent'),
        ('accountant', 'Accountant'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teacher')
    phone_number = models.CharField(max_length=15, blank=True)
    is_active = models.BooleanField(default=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.get_full_name()} ({self.role}) - {self.username}'

    @property
    def full_name(self):
        return self.get_full_name() or self.username

    def is_admin(self):
        return self.role == 'admin' or self.is_superuser

    def is_teacher(self):
        return self.role == 'teacher'

    def is_parent(self):
        return self.role == 'parent'

    def is_accountant(self):
        return self.role == 'accountant'
