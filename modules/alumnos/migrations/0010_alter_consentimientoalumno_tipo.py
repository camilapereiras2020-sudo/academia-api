# Generated manually (no local Django env in this session) — mirrors what
# `python manage.py makemigrations alumnos` would produce for the new
# "politica_cancelacion" choice added to ConsentimientoAlumno.tipo.
# Please run `python manage.py makemigrations --check` locally before
# applying, to confirm Django doesn't see any other pending model change.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0009_inscripcion_alter_alumno_grupos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='consentimientoalumno',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('autorizacion_imagen', 'Autorización de imagen'),
                    ('proteccion_datos', 'Protección de datos'),
                    ('matricula', 'Matrícula'),
                    ('politica_cancelacion', 'Política de cancelación'),
                ],
                max_length=25,
            ),
        ),
    ]
