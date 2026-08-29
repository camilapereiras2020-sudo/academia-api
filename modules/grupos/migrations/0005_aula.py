import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_aulas_from_grupos(apps, schema_editor):
    """Create an Aula row (with a codigo) for every distinct non-blank
    Grupo.aula string already in use, per academia — so existing rooms get a
    código too, not just ones typed after this migration. Grupo.aula itself
    is untouched; this is purely an additive lookup table."""
    Grupo = apps.get_model("grupos", "Grupo")
    Aula = apps.get_model("grupos", "Aula")
    for academia_id in Grupo.objects.values_list("academia_id", flat=True).distinct():
        nombres = (
            Grupo.objects.filter(academia_id=academia_id)
            .exclude(aula="")
            .values_list("aula", flat=True)
            .distinct()
            .order_by("aula")
        )
        for i, nombre in enumerate(nombres, start=1):
            Aula.objects.get_or_create(
                academia_id=academia_id, nombre=nombre,
                defaults={"codigo": f"A{i}"},
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('grupos', '0004_grupo_profesor'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Aula',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100)),
                ('codigo', models.CharField(blank=True, max_length=20)),
                ('activo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('academia', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aulas', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['nombre']},
        ),
        migrations.AddConstraint(
            model_name='aula',
            constraint=models.UniqueConstraint(fields=('academia', 'nombre'), name='unique_aula_por_academia_nombre'),
        ),
        migrations.RunPython(backfill_aulas_from_grupos, noop),
    ]
