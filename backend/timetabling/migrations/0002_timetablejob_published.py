# Generated manually — add to backend/timetabling/migrations/

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('timetabling', '0001_initial'),  # adjust to your last migration
    ]

    operations = [
        migrations.AddField(
            model_name='timetablejob',
            name='published',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='timetablejob',
            name='published_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]