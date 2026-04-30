from django.db import models


class SchoolBranding(models.Model):
    school_name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to='branding/logos/', null=True, blank=True)
    favicon = models.ImageField(upload_to='branding/favicons/', null=True, blank=True)
    primary_color = models.CharField(max_length=7, default='#1a73e8', help_text='Hex color code e.g. #1a73e8')
    secondary_color = models.CharField(max_length=7, default='#34a853', help_text='Hex color code')
    accent_color = models.CharField(max_length=7, default='#fbbc04', help_text='Hex color code')
    motto = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    county = models.CharField(max_length=50, blank=True, help_text='Kenyan county')
    sub_county = models.CharField(max_length=50, blank=True)
    ward = models.CharField(max_length=50, blank=True)
    established_year = models.PositiveSmallIntegerField(null=True, blank=True)
    knec_code = models.CharField(max_length=20, blank=True, help_text='KNEC school code')
    nemis_code = models.CharField(max_length=20, blank=True, help_text='NEMIS school code')
    school_type = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Public'),
            ('private', 'Private'),
            ('mission', 'Mission'),
            ('international', 'International'),
        ],
        default='private',
    )
    curriculum = models.CharField(
        max_length=10,
        choices=[('CBC', 'CBC'), ('IGCSE', 'IGCSE'), ('IB', 'IB'), ('mixed', 'Mixed')],
        default='CBC',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'School Branding'
        verbose_name_plural = 'School Branding'

    def __str__(self):
        return f'{self.school_name} Branding'
