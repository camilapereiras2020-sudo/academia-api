from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documentos', '0008_emisor_invoice_counters'),
    ]

    operations = [
        migrations.AddField(
            model_name='documento',
            name='pdf_data',
            field=models.BinaryField(blank=True, editable=False, null=True),
        ),
    ]
