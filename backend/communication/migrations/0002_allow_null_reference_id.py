from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smslog',
            name='reference_id',
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
        migrations.RunSQL(
            sql="UPDATE communication_smslog SET reference_id = NULL WHERE reference_id = ''",
            reverse_sql="UPDATE communication_smslog SET reference_id = '' WHERE reference_id IS NULL",
        ),
    ]
