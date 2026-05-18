from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0005_alter_payment_payment_method_alter_payment_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentfee',
            name='credit',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
