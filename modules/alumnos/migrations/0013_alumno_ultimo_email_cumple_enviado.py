# Generated manually (no local Django env in this session) — mirrors what
# `python manage.py makemigrations alumnos` would produce for the new
# `ultimo_email_cumple_enviado` field on Alumno.
# Please run `python manage.py makemigrations --check` locally before
# applying, to confirm Django doesn't see any other pending model change.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0012_alumno_curso'),
    ]

    operations = [
        migrations.AddField(
            model_name='alumno',
            name='ultimo_email_cumple_enviado',
            field=models.DateField(blank=True, null=True),
        ),
    ]
