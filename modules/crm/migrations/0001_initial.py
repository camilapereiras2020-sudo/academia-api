from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("alumnos", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Lead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("nombre_contacto", models.CharField(max_length=200)),
                ("nombre_alumno", models.CharField(max_length=200)),
                ("edad_alumno", models.PositiveIntegerField(null=True, blank=True)),
                ("curso_escolar", models.CharField(max_length=50, blank=True)),
                ("telefono", models.CharField(max_length=20)),
                ("objetivo", models.CharField(max_length=20, default="general")),
                ("email", models.EmailField(blank=True)),
                ("nivel_estimado", models.CharField(max_length=10, blank=True)),
                ("disponibilidad", models.TextField(blank=True)),
                ("colegio", models.CharField(max_length=200, blank=True)),
                ("necesidades_especiales", models.TextField(blank=True)),
                ("origen", models.CharField(max_length=20, default="telefono")),
                ("notas", models.TextField(blank=True)),
                ("etapa", models.CharField(max_length=20, default="nueva_consulta")),
                ("proximo_seguimiento", models.DateField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("academia", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="leads",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("alumno", models.OneToOneField(
                    null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="lead",
                    to="alumnos.alumno",
                )),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="Interaccion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("tipo", models.CharField(max_length=20)),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                ("resumen", models.TextField()),
                ("proxima_accion", models.TextField(blank=True)),
                ("lead", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="interacciones",
                    to="crm.lead",
                )),
            ],
            options={"ordering": ["-fecha"]},
        ),
    ]
