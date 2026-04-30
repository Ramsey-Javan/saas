from django.db import models
from django.conf import settings


GRADE_CHOICES = [
    ('PP1', 'Pre-Primary 1'),
    ('PP2', 'Pre-Primary 2'),
    ('G1', 'Grade 1'),
    ('G2', 'Grade 2'),
    ('G3', 'Grade 3'),
    ('G4', 'Grade 4'),
    ('G5', 'Grade 5'),
    ('G6', 'Grade 6'),
    ('G7', 'Grade 7'),
    ('G8', 'Grade 8'),
    ('G9', 'Grade 9'),
    ('G10', 'Grade 10'),
    ('G11', 'Grade 11'),
    ('G12', 'Grade 12'),
]

GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]


class Student(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    other_names = models.CharField(max_length=100, blank=True)
    admission_number = models.CharField(max_length=20, unique=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    grade_level = models.CharField(max_length=5, choices=GRADE_CHOICES)
    stream = models.CharField(max_length=50, blank=True, help_text='e.g. East, West, North, South')
    photo = models.ImageField(upload_to='students/photos/', null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Parent/Guardian Info
    parent_name = models.CharField(max_length=200)
    parent_phone = models.CharField(max_length=15)
    parent_email = models.EmailField(blank=True)
    parent_relationship = models.CharField(
        max_length=20,
        choices=[
            ('father', 'Father'), ('mother', 'Mother'),
            ('guardian', 'Guardian'), ('other', 'Other'),
        ],
        default='guardian',
    )
    parent_occupation = models.CharField(max_length=100, blank=True)
    parent_address = models.TextField(blank=True)

    # Optional secondary contact
    secondary_contact_name = models.CharField(max_length=200, blank=True)
    secondary_contact_phone = models.CharField(max_length=15, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.last_name} {self.first_name} ({self.admission_number})'

    @property
    def full_name(self):
        names = [self.first_name, self.other_names, self.last_name]
        return ' '.join(n for n in names if n)

    @property
    def grade_display(self):
        return dict(GRADE_CHOICES).get(self.grade_level, self.grade_level)


class Admission(models.Model):
    ADMISSION_TYPE_CHOICES = [
        ('new', 'New Admission'),
        ('transfer', 'Transfer'),
        ('readmission', 'Re-Admission'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='admissions')
    academic_year = models.CharField(max_length=9, help_text='e.g. 2024/2025')
    date_admitted = models.DateField()
    admission_type = models.CharField(max_length=20, choices=ADMISSION_TYPE_CHOICES, default='new')
    previous_school = models.CharField(max_length=200, blank=True)
    grade_on_admission = models.CharField(max_length=5, choices=GRADE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='approved')
    notes = models.TextField(blank=True)
    admitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admissions_processed',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Admission'
        verbose_name_plural = 'Admissions'
        ordering = ['-date_admitted']

    def __str__(self):
        return f'{self.student} - {self.academic_year} ({self.status})'
