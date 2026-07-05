"""Seed known ConceptoAlias entries (nicknames / recurring Bizum-text
variants that matching.best_match() can't resolve on its own).

Not wired into the Procfile release phase — run manually once after
this migrates:
    python manage.py seed_concepto_alias
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from modules.alumnos.models import Alumno
from modules.pagos.models import ConceptoAlias

User = get_user_model()

# alias_text -> (alumno_nombre_exact, pagador_nombre_exact | None)
# NOTE: "Ramirez Gonzalez Arturo" / "Arturo" intentionally NOT seeded here —
# no alumno or pagador named Arturo exists anywhere in the DB, and the
# alumno this was guessed to relate to (Alba Ramírez Martín) is her own
# self-pay pagador, not a distinct "Arturo". Needs a human decision before
# any alias can be added for it.
SEEDS = [
    ("Tete", "Tere", None),
]


class Command(BaseCommand):
    help = "Seed known ConceptoAlias entries"

    def handle(self, *args, **options):
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("No hay usuarios en la base de datos."))
            return

        for alias_text, alumno_nombre, pagador_nombre in SEEDS:
            alumno = Alumno.objects.filter(academia=user, nombre=alumno_nombre).first() if alumno_nombre else None
            if alumno_nombre and not alumno:
                self.stdout.write(self.style.ERROR(f"SKIP {alias_text!r}: alumno {alumno_nombre!r} no encontrado"))
                continue

            alias, created = ConceptoAlias.objects.get_or_create(
                academia=user, alias_text=alias_text,
                defaults={"alumno": alumno, "pagador": None},
            )
            verb = "Creado" if created else "Ya existía"
            self.stdout.write(self.style.SUCCESS(f"{verb}: {alias_text!r} -> alumno {alumno_nombre!r}"))
