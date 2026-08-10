from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('timetabling', '0002_timetablejob_published'),
    ]

    operations = [
        migrations.AddField(
            model_name='subjectrule',
            name='stream',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Optional. Matches students.Classroom.stream exactly (e.g. "West"). '
                    'Leave blank to apply this rule to every stream in the grade.'
                ),
                max_length=10,
            ),
        ),
        migrations.AlterUniqueTogether(
            name='subjectrule',
            unique_together={('tenant', 'subject', 'grade_band', 'stream')},
        ),
        migrations.AlterModelOptions(
            name='subjectrule',
            options={'ordering': ['grade_band', 'stream', 'subject__name']},
        ),
    ]