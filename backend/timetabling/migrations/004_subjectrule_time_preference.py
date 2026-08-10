from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('timetabling', '0003_subjectrule_stream'),
    ]

    operations = [
        migrations.AddField(
            model_name='subjectrule',
            name='time_preference',
            field=models.CharField(
                choices=[
                    ('none', 'No preference'),
                    ('prefer_morning', 'Prefer morning'),
                    ('strong_morning', 'Strongly prefer morning'),
                    ('prefer_afternoon', 'Prefer afternoon'),
                ],
                default='none',
                help_text=(
                    'Soft scheduling preference for time of day. Never blocks generation — '
                    'the solver will still use an off-preference slot rather than fail to schedule.'
                ),
                max_length=20,
            ),
        ),
    ]