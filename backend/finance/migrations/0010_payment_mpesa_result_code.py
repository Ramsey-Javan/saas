# Generated manually for mpesa_result_code field
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0009_alter_payment_student_fee_receiptcounter'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='mpesa_result_code',
            field=models.CharField(
                blank=True,
                default='',
                db_index=True,
                help_text='Daraja result code from callback',
                max_length=10,
            ),
            preserve_default=False,
        ),
    ]