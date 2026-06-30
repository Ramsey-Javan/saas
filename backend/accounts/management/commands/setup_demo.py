from django.core.management.base import BaseCommand

from accounts.models import CustomUser
from tenants.models import Tenant, Domain
from students.models import Classroom, Guardian, Student


class Command(BaseCommand):
    help = 'Seed two demo schools with separate admins, staff, students, and a platform superadmin.'

    def add_arguments(self, parser):
        parser.add_argument('--superadmin-email', default='superadmin@platform.co.ke')
        parser.add_argument('--superadmin-password', default='superadmin123')

    def create_school(self, name, slug, domain, admin_email, admin_password,
                      admin_first_name, admin_last_name, teachers_data, bursar_data,
                      classroom_name, classroom_grade, students_data, **tenant_defaults):
        """Create a complete school with tenant, domain, admin, teachers, bursar, classroom, students."""

        # =======================================
        # CREATE TENANT
        # =======================================
        tenant, tenant_created = Tenant.objects.get_or_create(
            name=name,
            defaults={
                'slug': slug,
                'domain': domain,
                'registration_number': tenant_defaults.get('registration_number', f'{slug.upper()}-0001'),
                'motto': tenant_defaults.get('motto', 'Learning made simple'),
                'description': tenant_defaults.get('description', f'{name} demo school.'),
                'email': tenant_defaults.get('email', admin_email),
                'phone': tenant_defaults.get('phone', '0700000000'),
                'address': tenant_defaults.get('address', 'Nairobi, Kenya'),
                'county': tenant_defaults.get('county', 'Nairobi'),
                'sub_county': tenant_defaults.get('sub_county', 'Westlands'),
                'primary_color': tenant_defaults.get('primary_color', '#1e40af'),
                'secondary_color': tenant_defaults.get('secondary_color', '#ffffff'),
                'accent_color': tenant_defaults.get('accent_color', '#f59e0b'),
                'school_type': tenant_defaults.get('school_type', Tenant.SchoolType.COMBINED),
                'is_active': True,
            },
        )

        if not tenant_created and tenant.domain != domain:
            tenant.domain = domain
            tenant.save(update_fields=['domain'])

        # ====================================
        # CREATE DOMAIN
        # ====================================
        Domain.objects.get_or_create(
            tenant=tenant,
            defaults={
                'domain_name': slug,
                'is_primary': True,
                'verified': True,
            },
        )

        # ====================================
        # CREATE ADMIN USER
        # ====================================
        admin, admin_created = CustomUser.objects.get_or_create(
            email=admin_email,
            defaults={
                'username': admin_email,
                'first_name': admin_first_name,
                'last_name': admin_last_name,
                'role': 'admin',
                'tenant': tenant,
                'is_staff': True,
                'is_superuser': True,
            },
        )

        if not admin_created:
            changed_fields = []
            if admin.first_name != admin_first_name:
                admin.first_name = admin_first_name
                changed_fields.append('first_name')
            if admin.last_name != admin_last_name:
                admin.last_name = admin_last_name
                changed_fields.append('last_name')
            if admin.role != 'admin':
                admin.role = 'admin'
                changed_fields.append('role')
            if admin.tenant_id != tenant.id:
                admin.tenant = tenant
                changed_fields.append('tenant')
            if not admin.is_staff:
                admin.is_staff = True
                changed_fields.append('is_staff')
            if not admin.is_superuser:
                admin.is_superuser = True
                changed_fields.append('is_superuser')
            if changed_fields:
                admin.save(update_fields=changed_fields)

        admin.set_password(admin_password)
        admin.save(update_fields=['password'])

        self.stdout.write(self.style.SUCCESS(
            f"Admin created: {admin.email} ({admin.get_full_name()}) — {tenant.name}"
        ))


        # ====================================
        # CREATE CLASSROOM
        # ====================================
        classroom, _ = Classroom.objects.get_or_create(
            tenant=tenant,
            name=classroom_name,
            stream='East',
            academic_year='2026',
            defaults={
                'grade_level': classroom_grade,
                'capacity': 40,
                'is_active': True,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"  Classroom: {classroom} — {tenant.name}"
        ))

        # ====================================
        # CREATE GUARDIANS + STUDENTS
        # ====================================
        created_students = []
        for data in students_data:
            guardian, _ = Guardian.objects.get_or_create(
                phone=data['guardian_phone'],
                defaults={
                    'first_name': data['guardian_first_name'],
                    'last_name': data['guardian_last_name'],
                    'relationship': data['guardian_relationship'],
                    'national_id': data['guardian_national_id'],
                    'is_primary': True,
                },
            )

            student, _ = Student.objects.get_or_create(
                admission_number=data['admission_number'],
                defaults={
                    'tenant': tenant,
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'gender': data['gender'],
                    'date_of_birth': data['date_of_birth'],
                    'classroom': classroom,
                    'primary_guardian': guardian,
                    'status': Student.Status.ACTIVE,
                    'is_active': True,
                },
            )
            created_students.append(student)
            self.stdout.write(self.style.SUCCESS(
                f"    Student: {student.get_full_name()} ({student.admission_number}) — {tenant.name}"
            ))

        return {
            'tenant': tenant,
            'admin': admin,
            'classroom': classroom,
            'students': created_students,
        }

    def handle(self, *args, **options):
        superadmin_email = options['superadmin_email']
        superadmin_password = options['superadmin_password']

        # ====================================
        # CREATE PLATFORM SUPERADMIN
        # (tenant=None — platform-wide, no school)
        # ====================================
        tenant_field = CustomUser._meta.get_field('tenant')
        superadmin_tenant = None if tenant_field.null else None

        superadmin, superadmin_created = CustomUser.objects.get_or_create(
            email=superadmin_email,
            defaults={
                'username': superadmin_email,
                'first_name': 'Platform',
                'last_name': 'Superadmin',
                'role': 'superadmin',
                'tenant': superadmin_tenant,
                'is_staff': True,
                'is_superuser': True,
            },
        )

        if not superadmin_created:
            changed_fields = []
            if superadmin.role != 'superadmin':
                superadmin.role = 'superadmin'
                changed_fields.append('role')
            if not superadmin.is_staff:
                superadmin.is_staff = True
                changed_fields.append('is_staff')
            if not superadmin.is_superuser:
                superadmin.is_superuser = True
                changed_fields.append('is_superuser')
            if changed_fields:
                superadmin.save(update_fields=changed_fields)

        superadmin.set_password(superadmin_password)
        superadmin.save(update_fields=['password'])

        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*50}\n"
            f"PLATFORM SUPERADMIN\n"
            f"{'='*50}\n"
            f"Email:    {superadmin.email}\n"
            f"Password: {superadmin_password}\n"
            f"Tenant:   None (platform-wide)\n"
        ))

        # ====================================
        # SCHOOL 1: DEMO SCHOOL
        # ====================================
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'='*50}\nSCHOOL 1: DEMO SCHOOL\n{'='*50}"
        ))

        school1 = self.create_school(
            name='Demo School',
            slug='demo-school',
            domain='http://demo.localhost',
            admin_email='admin@demo.co.ke',
            admin_password='demo1234',
            admin_first_name='Demo',
            admin_last_name='Admin',
            teachers_data=[
                {'email': 'john.mwangi@demo.co.ke', 'first_name': 'John', 'last_name': 'Mwangi'},
                {'email': 'mary.atieno@demo.co.ke', 'first_name': 'Mary', 'last_name': 'Atieno'},
                {'email': 'kevin.bosire@demo.co.ke', 'first_name': 'Kevin', 'last_name': 'Bosire'},
                {'email': 'esther.njeri@demo.co.ke', 'first_name': 'Esther', 'last_name': 'Njeri'},
                {'email': 'brian.otieno@demo.co.ke', 'first_name': 'Brian', 'last_name': 'Otieno'},
            ],
            bursar_data={'email': 'grace.wambui@demo.co.ke', 'first_name': 'Grace', 'last_name': 'Wambui'},
            classroom_name='Grade 5',
            classroom_grade='Grade 5',
            students_data=[
                {'admission_number': 'DEMO/2026/001', 'first_name': 'Amani', 'last_name': 'Kamau', 'gender': 'M', 'date_of_birth': '2015-03-15', 'guardian_phone': '0711111111', 'guardian_first_name': 'Joseph', 'guardian_last_name': 'Kamau', 'guardian_relationship': 'father', 'guardian_national_id': '11111111'},
                {'admission_number': 'DEMO/2026/002', 'first_name': 'Faith', 'last_name': 'Wanjiru', 'gender': 'F', 'date_of_birth': '2015-06-02', 'guardian_phone': '0711111112', 'guardian_first_name': 'Susan', 'guardian_last_name': 'Wanjiru', 'guardian_relationship': 'mother', 'guardian_national_id': '11111112'},
                {'admission_number': 'DEMO/2026/003', 'first_name': 'Brian', 'last_name': 'Mutua', 'gender': 'M', 'date_of_birth': '2014-11-21', 'guardian_phone': '0711111113', 'guardian_first_name': 'Michael', 'guardian_last_name': 'Mutua', 'guardian_relationship': 'father', 'guardian_national_id': '11111113'},
                {'admission_number': 'DEMO/2026/004', 'first_name': 'Grace', 'last_name': 'Achieng', 'gender': 'F', 'date_of_birth': '2015-01-09', 'guardian_phone': '0711111114', 'guardian_first_name': 'Esther', 'guardian_last_name': 'Achieng', 'guardian_relationship': 'mother', 'guardian_national_id': '11111114'},
                {'admission_number': 'DEMO/2026/005', 'first_name': 'Daniel', 'last_name': 'Kiptoo', 'gender': 'M', 'date_of_birth': '2014-09-30', 'guardian_phone': '0711111115', 'guardian_first_name': 'James', 'guardian_last_name': 'Kiptoo', 'guardian_relationship': 'father', 'guardian_national_id': '11111115'},
            ],
            registration_number='DEMO-0001',
            motto='Learning made simple',
            description='First demo school for testing.',
            email='info@demo.co.ke',
            phone='0700000001',
            address='Westlands, Nairobi',
            county='Nairobi',
            sub_county='Westlands',
            primary_color='#1e40af',
            secondary_color='#ffffff',
            accent_color='#f59e0b',
        )

        # ====================================
        # SCHOOL 2: ALPHA ACADEMY
        # ====================================
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'='*50}\nSCHOOL 2: ALPHA ACADEMY\n{'='*50}"
        ))

        school2 = self.create_school(
            name='Alpha Academy',
            slug='alpha-academy',
            domain='http://alpha.localhost',
            admin_email='admin@alpha.co.ke',
            admin_password='alpha1234',
            admin_first_name='Alpha',
            admin_last_name='Principal',
            teachers_data=[
                {'email': 'peter.ndungu@alpha.co.ke', 'first_name': 'Peter', 'last_name': 'Ndungu'},
                {'email': 'jane.wanjiku@alpha.co.ke', 'first_name': 'Jane', 'last_name': 'Wanjiku'},
                {'email': 'samuel.kipchirchir@alpha.co.ke', 'first_name': 'Samuel', 'last_name': 'Kipchirchir'},
                {'email': 'lucy.muthoni@alpha.co.ke', 'first_name': 'Lucy', 'last_name': 'Muthoni'},
            ],
            bursar_data={'email': 'james.ombui@alpha.co.ke', 'first_name': 'James', 'last_name': 'Ombui'},
            classroom_name='Grade 7',
            classroom_grade='Grade 7',
            students_data=[
                {'admission_number': 'ALPHA/2026/001', 'first_name': 'Caleb', 'last_name': 'Ochieng', 'gender': 'M', 'date_of_birth': '2013-04-12', 'guardian_phone': '0722222221', 'guardian_first_name': 'David', 'guardian_last_name': 'Ochieng', 'guardian_relationship': 'father', 'guardian_national_id': '22222221'},
                {'admission_number': 'ALPHA/2026/002', 'first_name': 'Naomi', 'last_name': 'Wangari', 'gender': 'F', 'date_of_birth': '2013-08-25', 'guardian_phone': '0722222222', 'guardian_first_name': 'Grace', 'guardian_last_name': 'Wangari', 'guardian_relationship': 'mother', 'guardian_national_id': '22222222'},
                {'admission_number': 'ALPHA/2026/003', 'first_name': 'Elijah', 'last_name': 'Kamau', 'gender': 'M', 'date_of_birth': '2012-12-03', 'guardian_phone': '0722222223', 'guardian_first_name': 'John', 'guardian_last_name': 'Kamau', 'guardian_relationship': 'father', 'guardian_national_id': '22222223'},
                {'admission_number': 'ALPHA/2026/004', 'first_name': 'Sarah', 'last_name': 'Muthoni', 'gender': 'F', 'date_of_birth': '2013-01-18', 'guardian_phone': '0722222224', 'guardian_first_name': 'Mary', 'guardian_last_name': 'Muthoni', 'guardian_relationship': 'mother', 'guardian_national_id': '22222224'},
                {'admission_number': 'ALPHA/2026/005', 'first_name': 'Isaac', 'last_name': 'Kiprotich', 'gender': 'M', 'date_of_birth': '2012-09-07', 'guardian_phone': '0722222225', 'guardian_first_name': 'Daniel', 'guardian_last_name': 'Kiprotich', 'guardian_relationship': 'father', 'guardian_national_id': '22222225'},
            ],
            registration_number='ALPHA-0001',
            motto='Excellence in education',
            description='Second demo school for testing multi-tenancy.',
            email='info@alpha.co.ke',
            phone='0700000002',
            address='Kilimani, Nairobi',
            county='Nairobi',
            sub_county='Kilimani',
            primary_color='#059669',
            secondary_color='#f0fdf4',
            accent_color='#fbbf24',
            school_type=Tenant.SchoolType.JUNIOR_SECONDARY,
        )

        # ====================================
        # PLATFORM OVERVIEW
        # ====================================
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"{'='*50}\nPLATFORM OVERVIEW — ALL TENANTS\n{'='*50}"
        ))

        all_tenants = Tenant.objects.all().order_by('name')

        for t in all_tenants:
            user_count = CustomUser.objects.filter(tenant=t).count()
            teacher_count = CustomUser.objects.filter(tenant=t, role='teacher').count()
            bursar_count = CustomUser.objects.filter(tenant=t, role='bursar').count()
            admin_count = CustomUser.objects.filter(tenant=t, role='admin').count()
            student_count = Student.objects.filter(tenant=t).count()
            classroom_count = Classroom.objects.filter(tenant=t).count()
            status_label = 'ACTIVE' if t.is_active else 'INACTIVE'

            self.stdout.write(
                f"- {t.name} [{status_label}]\n"
                f"    domain: {t.domain}\n"
                f"    users: {user_count} "
                f"(admins: {admin_count}, teachers: {teacher_count}, bursars: {bursar_count})\n"
                f"    students: {student_count} | classrooms: {classroom_count}"
            )

        total_tenants = all_tenants.count()
        active_tenants = all_tenants.filter(is_active=True).count()
        total_students_platform = Student.objects.count()
        total_users_platform = CustomUser.objects.count()

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Total tenants: {total_tenants} '
            f'(active: {active_tenants}) | '
            f'Total users platform-wide: {total_users_platform} | '
            f'Total students platform-wide: {total_students_platform}'
        ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Seed complete!'))
        self.stdout.write('')
        self.stdout.write('Login credentials:')
        self.stdout.write(f'  Superadmin:  {superadmin_email} / {superadmin_password}')
        self.stdout.write(f'  Demo Admin:  admin@demo.co.ke / demo1234')
        self.stdout.write(f'  Alpha Admin: admin@alpha.co.ke / alpha1234')