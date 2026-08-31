# Generated manually (no local Django env in this session) — mirrors what
# `python manage.py makemigrations alumnos` would produce for the new
# motivo_baja/fecha_baja fields on Alumno.
# Please run `python manage.py makemigrations --check` locally before
# applying, to confirm Django doesn't see any other pending model change.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0010_alter_consentimientoalumno_tipo'),
    ]

    operations = [
        migrations.AddField(
            model_name='alumno',
            name='motivo_baja',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='alumno',
            name='fecha_baja',
            field=models.DateField(blank=True, null=True),
        ),
    ]
