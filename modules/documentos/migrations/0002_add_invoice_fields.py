from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documentos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="documento",
            name="num_doc",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="documento",
            name="local_path",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AlterField(
            model_name="documento",
            name="s3_key",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
