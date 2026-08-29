from django.db import migrations, models


def backfill_codigos(apps, schema_editor):
    Profesor = apps.get_model("profesores", "Profesor")
    for academia_id in Profesor.objects.values_list("academia_id", flat=True).distinct():
        qs = Profesor.objects.filter(academia_id=academia_id).order_by("orden", "nombre", "id")
        for i, profesor in enumerate(qs, start=1):
            profesor.codigo = f"P{i}"
            profesor.save(update_fields=["codigo"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('profesores', '0002_seed_default_profesores'),
    ]

    operations = [
        migrations.AddField(
            model_name='profesor',
            name='codigo',
            field=models.CharField(max_length=20, blank=True),
        ),
        migrations.RunPython(backfill_codigos, noop),
    ]
