from django.db import migrations


DEFAULT_PROFESORES = [
    ("Cami", False, 0),
    ("Cande", False, 1),
    ("Suplente", True, 2),
]


def seed_profesores(apps, schema_editor):
    User = apps.get_model("authentication", "User")
    Profesor = apps.get_model("profesores", "Profesor")

    # Only seed for real academia owners (role="owner"), never for co_manager/
    # reception accounts, which share their owner's tenant data.
    for owner in User.objects.filter(role="owner"):
        for nombre, es_suplente, orden in DEFAULT_PROFESORES:
            Profesor.objects.get_or_create(
                academia=owner,
                nombre=nombre,
                defaults={"es_suplente": es_suplente, "orden": orden},
            )


def noop_reverse(apps, schema_editor):
    # Deliberately not removing rows on reverse — a rollback shouldn't
    # silently delete data a user may already be relying on / have edited.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("profesores", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_profesores, noop_reverse),
    ]
