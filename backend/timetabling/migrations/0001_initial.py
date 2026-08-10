from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('academics', '0005_attendancesession_auto_marked_and_more'),
        ('students', '0004_guardian_tenant'),
        ('tenants', '0003_tenant_attendance_auto_lock_days'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduleTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={'ordering': ['name'], 'unique_together': {('tenant', 'name')}},
        ),
        migrations.CreateModel(
            name='RoomResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('room_type', models.CharField(choices=[('classroom', 'Classroom'), ('lab', 'Lab'), ('hall', 'Hall'), ('library', 'Library'), ('field', 'Field'), ('other', 'Other')], max_length=20)),
                ('capacity', models.PositiveIntegerField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={'ordering': ['room_type', 'name'], 'unique_together': {('tenant', 'name')}},
        ),
        migrations.CreateModel(
            name='TimetableJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('term', models.CharField(choices=[('term1', 'Term 1'), ('term2', 'Term 2'), ('term3', 'Term 3')], max_length=10)),
                ('academic_year', models.PositiveIntegerField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('done', 'Done'), ('failed', 'Failed')], default='pending', max_length=10)),
                ('current_score', models.FloatField(blank=True, null=True)),
                ('best_bound', models.FloatField(blank=True, null=True)),
                ('failure_reason', models.TextField(blank=True)),
                ('solve_time_seconds', models.FloatField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_timetable_jobs', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Period',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_of_week', models.PositiveSmallIntegerField(choices=[(1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'), (4, 'Thursday'), (5, 'Friday'), (6, 'Saturday'), (7, 'Sunday')])),
                ('order', models.PositiveSmallIntegerField()),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('is_break', models.BooleanField(default=False)),
                ('schedule_template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='periods', to='timetabling.scheduletemplate')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={'ordering': ['schedule_template', 'day_of_week', 'order'], 'unique_together': {('tenant', 'schedule_template', 'day_of_week', 'order')}},
        ),
        migrations.CreateModel(
            name='SubjectRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('grade_band', models.CharField(help_text='Matches students.Classroom.grade_level for this tenant.', max_length=50)),
                ('periods_per_week', models.PositiveSmallIntegerField(default=0)),
                ('requires_double', models.BooleanField(default=False)),
                ('requires_room_type', models.CharField(blank=True, choices=[('classroom', 'Classroom'), ('lab', 'Lab'), ('hall', 'Hall'), ('library', 'Library'), ('field', 'Field'), ('other', 'Other')], max_length=20, null=True)),
                ('is_hard_excluded', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('excluded_periods', models.ManyToManyField(blank=True, related_name='excluded_by_rules', to='timetabling.period')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetable_rules', to='academics.subject')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={'ordering': ['grade_band', 'subject__name'], 'unique_together': {('tenant', 'subject', 'grade_band')}},
        ),
        migrations.CreateModel(
            name='TeacherAvailability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_available', models.BooleanField(default=True)),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_availability', to='timetabling.period')),
                ('teacher', models.ForeignKey(limit_choices_to={'role': 'teacher'}, on_delete=django.db.models.deletion.CASCADE, related_name='timetable_availability', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={'ordering': ['teacher__last_name', 'period__day_of_week', 'period__order'], 'unique_together': {('tenant', 'teacher', 'period')}},
        ),
        migrations.CreateModel(
            name='TeacherSubjectAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('classroom', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetable_assignments', to='students.classroom')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetable_assignments', to='academics.subject')),
                ('teacher', models.ForeignKey(limit_choices_to={'role': 'teacher'}, on_delete=django.db.models.deletion.CASCADE, related_name='timetable_subject_assignments', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={'ordering': ['classroom__name', 'subject__name'], 'unique_together': {('tenant', 'teacher', 'subject', 'classroom')}},
        ),
        migrations.CreateModel(
            name='TeacherWorkloadLimit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('max_periods_per_day', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('max_periods_per_week', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('teacher', models.OneToOneField(limit_choices_to={'role': 'teacher'}, on_delete=django.db.models.deletion.CASCADE, related_name='timetable_workload_limit', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={'ordering': ['teacher__last_name']},
        ),
        migrations.CreateModel(
            name='TimetableEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('locked', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('classroom', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='generated_timetable_entries', to='students.classroom')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='timetabling.timetablejob')),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='generated_entries', to='timetabling.period')),
                ('room', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_entries', to='timetabling.roomresource')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='generated_timetable_entries', to='academics.subject')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='generated_timetable_entries', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={'ordering': ['period__day_of_week', 'period__order', 'classroom__name'], 'unique_together': {('job', 'classroom', 'period')}},
        ),
    ]

