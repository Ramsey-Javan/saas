from django.core.management.base import BaseCommand

from accounts.models import CustomUser
from tenants.models import Tenant, Domain
from students.models import Classroom, Guardian, Student


class Command(BaseCommand):
    help = 'Create or update a demo tenant and admin user for local development.'

    def add_arguments(self, parser):
        parser.add_argument('--email', default='admin@demo.co.ke')
        parser.add_argument('--password', default='demo1234')
        parser.add_argument('--first-name', default='Demo')
        parser.add_argument('--last-name', default='Admin')
        parser.add_argument('--tenant-name', default='Demo School')
        parser.add_argument('--tenant-domain', default='http://demo.localhost')

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        first_name = options['first_name']
        last_name = options['last_name']
        tenant_name = options['tenant_name']
        tenant_domain = options['tenant_domain']

        tenant, tenant_created = Tenant.objects.get_or_create(
            name=tenant_name,
            defaults={
                'domain': tenant_domain,
                'registration_number': 'DEMO-0001',
                'motto': 'Learning made simple',
                'description': 'Local development demo school.',
                'email': email,
                'phone': '0700000000',
                'address': 'Nairobi, Kenya',
                'county': 'Nairobi',
                'sub_county': 'Westlands',
                'primary_color': '#1e40af',
                'secondary_color': '#ffffff',
                'accent_color': '#f59e0b',
                'is_active': True,
            },
        )

        if not tenant_created and tenant.domain != tenant_domain:
            tenant.domain = tenant_domain
            tenant.save(update_fields=['domain'])

        Domain.objects.get_or_create(
            tenant=tenant,
            defaults={
                'domain_name': 'demo.localhost',
                'is_primary': True,
                'verified': True,
            },
        )

        user, user_created = CustomUser.objects.get_or_create(
            email=email,
            defaults={
                'username': email,
                'first_name': first_name,
                'last_name': last_name,
                'role': 'admin',
                'tenant': tenant,
                'is_staff': True,
                'is_superuser': True,
            },
        )

        if not user_created:
            changed_fields = []
            if user.first_name != first_name:
                user.first_name = first_name
                changed_fields.append('first_name')
            if user.last_name != last_name:
                user.last_name = last_name
                changed_fields.append('last_name')
            if user.role != 'admin':
                user.role = 'admin'
                changed_fields.append('role')
            if user.tenant_id != tenant.id:
                user.tenant = tenant
                changed_fields.append('tenant')
            if not user.is_staff:
                user.is_staff = True
                changed_fields.append('is_staff')
            if not user.is_superuser:
                user.is_superuser = True
                changed_fields.append('is_superuser')
            if changed_fields:
                user.save(update_fields=changed_fields)

        if password:
            user.set_password(password)
            user.save(update_fields=['password'])

        classroom, _ = Classroom.objects.get_or_create(
            tenant=tenant,
            name='Grade 5',
            stream='East',
            academic_year='2026',
            defaults={
                'grade_level': 'Grade 5',
                'capacity': 40,
                'is_active': True,
            },
        )

        guardian, _ = Guardian.objects.get_or_create(
            phone='0712345678',
            defaults={
                'first_name': 'Joseph',
                'last_name': 'Kamau',
                'relationship': 'father',
                'national_id': '23456789',
                'is_primary': True,
            },
        )

        student, _ = Student.objects.get_or_create(
            admission_number='ADM/2026/001',
            defaults={
                'tenant': tenant,
                'first_name': 'Amani',
                'last_name': 'Kamau',
                'gender': 'M',
                'date_of_birth': '2015-03-15',
                'classroom': classroom,
                'primary_guardian': guardian,
                'status': Student.Status.ACTIVE,
                'is_active': True,
            },
        )

        self.stdout.write(self.style.SUCCESS('Demo setup complete.'))
        self.stdout.write(f'Email: {email}')
        self.stdout.write(f'Password: {password}')
        self.stdout.write(f'Tenant: {tenant.name}')
        self.stdout.write(f'Classroom: {classroom}')
        self.stdout.write(f'Guardian: {guardian.full_name}')
        self.stdout.write(f'Student: {student.get_full_name()}')
