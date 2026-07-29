from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0007_lead_marca'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='last_contacted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
