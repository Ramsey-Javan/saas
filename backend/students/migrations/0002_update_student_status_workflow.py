from django.db import migrations, models


def migrate_legacy_statuses(apps, schema_editor):
    Student = apps.get_model('students', 'Student')
    Student.objects.filter(status='withdrawn').update(status='dropped')
    Student.objects.filter(status='inactive').update(status='dropped')


def restore_legacy_statuses(apps, schema_editor):
    Student = apps.get_model('students', 'Student')
    Student.objects.filter(status='dropped').update(status='withdrawn')


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_statuses, restore_legacy_statuses),
        migrations.AlterField(
            model_name='student',
            name='status',
            field=models.CharField(
                choices=[
                    ('active', 'Active'),
                    ('transferred', 'Transferred'),
                    ('graduated', 'Graduated'),
                    ('dropped', 'Dropped'),
                ],
                default='active',
                max_length=20,
            ),
        ),
    ]
