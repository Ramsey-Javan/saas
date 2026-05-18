from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0002_rebuild_empty_finance_schema'),
    ]

    operations = [
        migrations.AddField(
            model_name='feestructure',
            name='due_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='feestructure',
            name='academic_year',
            field=models.IntegerField(),
        ),
    ]
