"""Seed known ConceptoAlias entries (nicknames / recurring Bizum-text
variants that matching.best_match() can't resolve on its own).

Not wired into the Procfile release phase — run manually once after
this migrates:
    python manage.py seed_concepto_alias
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from modules.alumnos.models import Alumno
from modules.pagadores.models import Pagador
from modules.pagos.models import ConceptoAlias

User = get_user_model()

# alias_text -> (alumno_nombre_exact | None, pagador_nombre_exact | None)
SEEDS = [
    # "Tete"/"Tere" never share a token with "Mª Teresa" (the "M" in "Mª"
    # is dropped as a length-1 token, leaving "teresa" — which still never
    # appears in either Bizum variant). Alumno side self-resolves for
    # "Tere" via direct name match already; only the pagador side needs
    # the alias, for both spellings.
    ("Tete", "Tere", "Mª Teresa"),
    ("Tere", None, "Mª Teresa"),
    # Resolved 2026-07-06: Arturo Ramírez confirmed as Alba's primary
    # pagador (Montse, the other parent, waits on the multi-payer model).
    ("Ramirez Gonzalez Arturo", "Alba Ramírez Martín", "Arturo Ramírez"),
    ("Arturo", "Alba Ramírez Martín", "Arturo Ramírez"),
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

            pagador = Pagador.objects.filter(academia=user, nombre=pagador_nombre).first() if pagador_nombre else None
            if pagador_nombre and not pagador:
                self.stdout.write(self.style.ERROR(f"SKIP {alias_text!r}: pagador {pagador_nombre!r} no encontrado"))
                continue

            _, created = ConceptoAlias.objects.update_or_create(
                academia=user, alias_text=alias_text,
                defaults={"alumno": alumno, "pagador": pagador},
            )
            verb = "Creado" if created else "Actualizado"
            self.stdout.write(self.style.SUCCESS(
                f"{verb}: {alias_text!r} -> alumno={alumno_nombre!r} pagador={pagador_nombre!r}"
            ))
