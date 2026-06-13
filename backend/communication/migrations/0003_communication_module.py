# Generated manually for the communication module expansion.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0002_allow_null_reference_id'),
        ('students', '0003_student_staff_parent'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenants', '0002_add_school_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('category', models.CharField(choices=[('fee', 'Fee Related'), ('attendance', 'Attendance'), ('academic', 'Academic'), ('general', 'General'), ('exam', 'Examination')], max_length=20)),
                ('channel', models.CharField(choices=[('sms', 'SMS'), ('whatsapp', 'WhatsApp'), ('email', 'Email'), ('all', 'All Channels')], default='all', max_length=20)),
                ('subject', models.CharField(blank=True, max_length=200)),
                ('body', models.TextField()),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_templates', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'ordering': ['category', 'name'],
                'unique_together': {('tenant', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('template_vars', models.JSONField(default=dict)),
                ('channels', models.JSONField(default=list)),
                ('recipient_type', models.CharField(choices=[('class', 'Specific Class'), ('grade', 'Grade Level'), ('school', 'Entire School'), ('individual', 'Individual'), ('teachers', 'All Teachers'), ('staff', 'All Staff')], max_length=20)),
                ('recipient_grade', models.CharField(blank=True, max_length=20)),
                ('send_immediately', models.BooleanField(default=True)),
                ('scheduled_at', models.DateTimeField(blank=True, null=True)),
                ('is_recurring', models.BooleanField(default=False)),
                ('recurrence_rule', models.JSONField(default=dict)),
                ('next_run_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('scheduled', 'Scheduled'), ('sending', 'Sending'), ('sent', 'Sent'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='draft', max_length=15)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('total_recipients', models.PositiveIntegerField(default=0)),
                ('delivered_count', models.PositiveIntegerField(default=0)),
                ('failed_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('recipient_class', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='announcements', to='students.classroom')),
                ('recipient_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='targeted_announcements', to=settings.AUTH_USER_MODEL)),
                ('sent_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sent_announcements', to=settings.AUTH_USER_MODEL)),
                ('template', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='announcements', to='communication.messagetemplate')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.TextField(unique=True)),
                ('p256dh', models.TextField()),
                ('auth', models.TextField()),
                ('user_agent', models.CharField(blank=True, max_length=500)),
                ('is_active', models.BooleanField(default=True)),
                ('subscribed_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='push_subscriptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('tenant', 'user', 'endpoint')},
            },
        ),
        migrations.CreateModel(
            name='MessageLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(choices=[('sms', 'SMS'), ('whatsapp', 'WhatsApp'), ('email', 'Email'), ('inapp', 'In-App')], max_length=10)),
                ('recipient_phone', models.CharField(blank=True, max_length=20)),
                ('recipient_email', models.CharField(blank=True, max_length=200)),
                ('recipient_name', models.CharField(blank=True, max_length=200)),
                ('message_body', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('read', 'Read'), ('failed', 'Failed')], default='pending', max_length=10)),
                ('provider_message_id', models.CharField(blank=True, max_length=200)),
                ('provider_cost', models.CharField(blank=True, max_length=50)),
                ('failure_reason', models.TextField(blank=True)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('announcement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='communication.announcement')),
                ('recipient_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='received_messages', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'ordering': ['-sent_at'],
            },
        ),
        migrations.CreateModel(
            name='InAppNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('type', models.CharField(choices=[('fee_reminder', 'Fee Reminder'), ('attendance', 'Attendance Alert'), ('report_card', 'Report Card'), ('announcement', 'Announcement'), ('exam', 'Examination'), ('system', 'System')], max_length=20)),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('action_url', models.CharField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('announcement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='in_app_notifications', to='communication.announcement')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
