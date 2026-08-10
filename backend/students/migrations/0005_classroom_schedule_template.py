from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('timetabling', '0001_initial'),
        ('students', '0004_guardian_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroom',
            name='schedule_template',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='classrooms', to='timetabling.scheduletemplate'),
        ),
    ]
