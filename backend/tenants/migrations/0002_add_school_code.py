from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='school_code',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
