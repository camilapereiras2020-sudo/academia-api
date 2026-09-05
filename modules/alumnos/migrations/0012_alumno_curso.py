# Generated manually (no local Django env in this session) — mirrors what
# `python manage.py makemigrations alumnos` would produce for the new
# `curso` field on Alumno.
# Please run `python manage.py makemigrations --check` locally before
# applying, to confirm Django doesn't see any other pending model change.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0011_alumno_fecha_baja_alumno_motivo_baja'),
    ]

    operations = [
        migrations.AddField(
            model_name='alumno',
            name='curso',
            field=models.CharField(
                blank=True,
                choices=[
                    ('infantil_3', 'Infantil 3 años'), ('infantil_4', 'Infantil 4 años'),
                    ('infantil_5', 'Infantil 5 años'),
                    ('primaria_1', '1º Primaria'), ('primaria_2', '2º Primaria'), ('primaria_3', '3º Primaria'),
                    ('primaria_4', '4º Primaria'), ('primaria_5', '5º Primaria'), ('primaria_6', '6º Primaria'),
                    ('eso_1', '1º ESO'), ('eso_2', '2º ESO'), ('eso_3', '3º ESO'), ('eso_4', '4º ESO'),
                    ('bach_1', '1º Bachillerato'), ('bach_2', '2º Bachillerato'),
                    ('fp', 'Formación Profesional'), ('adulto', 'Adulto'), ('otro', 'Otro'),
                ],
                max_length=20,
            ),
        ),
    ]
