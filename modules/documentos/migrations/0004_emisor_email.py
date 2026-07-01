from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documentos", "0003_add_emisor_and_pago_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="emisor",
            name="email",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
