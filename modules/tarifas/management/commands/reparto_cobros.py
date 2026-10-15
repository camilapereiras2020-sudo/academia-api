"""Listado de cobros del mes por pagador, con a qué profesora (Cande / Cami)
corresponde cada alumno y cuánto le toca a cada una.

Pensado para el caso "todo se cobró en la cuenta de Cande": muestra cuánto
tiene que pasarle Cande a Cami (lo que corresponde a los alumnos de Cami).

Solo lectura — no crea ni modifica nada.

La profesora de cada pago sale del grupo del pago (Pago.grupo.profesor); si el
pago no tiene grupo, de los grupos del alumno — y solo si todos son de la
misma profesora. Lo que no se pueda asignar con certeza queda aparte, en
"SIN ASIGNAR", para revisarlo a mano: nunca se adivina.

Uso:
    python manage.py reparto_cobros
    python manage.py reparto_cobros --periodo 2026-10
    python manage.py reparto_cobros --periodo 2026-10 --incluir-pendientes
"""
from collections import defaultdict
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()

SIN_ASIGNAR = "SIN ASIGNAR"
QUIEN_RECIBE = "cami"  # a quien hay que pasarle lo suyo


def _profesora_de_pago(pago):
    """Nombre de la profesora a la que corresponde el pago, o None."""
    if pago.grupo_id and pago.grupo.profesor_id:
        return pago.grupo.profesor.nombre
    if pago.alumno_id:
        nombres = {
            i.grupo.profesor.nombre
            for i in pago.alumno.inscripciones.all()
            if i.grupo and i.grupo.profesor_id
        }
        if len(nombres) == 1:
            return nombres.pop()
    return None


def calcular_reparto(owner, periodo, solo_pagados=True):
    """Devuelve (por_pagador, totales).

    por_pagador: {pagador_nombre: [(alumno_nombre, profesora, importe), ...]}
    totales: {profesora: Decimal}
    """
    from modules.pagos.models import Pago

    qs = (
        Pago.objects.filter(academia=owner, periodo=periodo)
        .select_related("pagador", "alumno__pagador", "grupo__profesor")
        .prefetch_related("alumno__inscripciones__grupo__profesor")
    )
    if solo_pagados:
        qs = qs.filter(estado="pagado")

    por_pagador = defaultdict(list)
    totales = defaultdict(lambda: Decimal("0"))
    for pago in qs:
        profesora = _profesora_de_pago(pago) or SIN_ASIGNAR
        if pago.pagador_id:
            pagador = pago.pagador.nombre
        elif pago.alumno_id and pago.alumno.pagador_id:
            pagador = pago.alumno.pagador.nombre
        else:
            pagador = "(sin pagador)"
        alumno = pago.alumno.nombre if pago.alumno_id else "(sin alumno)"
        por_pagador[pagador].append((alumno, profesora, pago.total))
        totales[profesora] += pago.total
    return dict(por_pagador), dict(totales)


class Command(BaseCommand):
    help = "Cobros del mes por pagador y reparto entre Cande y Cami."

    def add_arguments(self, parser):
        parser.add_argument("--periodo", default=None, help="AAAA-MM (por defecto, el mes actual).")
        parser.add_argument(
            "--incluir-pendientes", action="store_true",
            help="Incluir también pagos pendientes/parciales (por defecto, solo los pagados).",
        )
        parser.add_argument("--academia-email", default=None)

    def handle(self, *args, **options):
        owner = (
            User.objects.filter(email=options["academia_email"], role="owner").first()
            if options["academia_email"]
            else User.objects.filter(role="owner").first()
        )
        if not owner:
            self.stderr.write(self.style.ERROR("No encontré ningún usuario 'owner'."))
            return

        periodo = options["periodo"] or timezone.now().strftime("%Y-%m")
        por_pagador, totales = calcular_reparto(
            owner, periodo, solo_pagados=not options["incluir_pendientes"]
        )

        estado = "pagados y pendientes" if options["incluir_pendientes"] else "pagados"
        self.stdout.write(self.style.SUCCESS(f"\n=== Cobros de {periodo} ({estado}) ===\n"))
        if not por_pagador:
            self.stdout.write("No hay pagos para ese período.")
            return

        for pagador in sorted(por_pagador):
            lineas = por_pagador[pagador]
            total_pagador = sum((imp for _, _, imp in lineas), Decimal("0"))
            self.stdout.write(f"{pagador}  —  total {total_pagador:.2f} €")
            for alumno, profesora, importe in sorted(lineas):
                self.stdout.write(f"    {alumno:35s} → {profesora:12s} {importe:>8.2f} €")
            self.stdout.write("")

        self.stdout.write(self.style.SUCCESS("=== Totales por profesora ==="))
        for profesora in sorted(totales):
            self.stdout.write(f"  {profesora:20s} {totales[profesora]:>10.2f} €")
        total_cobrado = sum(totales.values(), Decimal("0"))
        self.stdout.write(f"  {'TOTAL COBRADO':20s} {total_cobrado:>10.2f} €\n")

        a_cami = sum((v for k, v in totales.items() if QUIEN_RECIBE in k.lower()), Decimal("0"))
        self.stdout.write(self.style.SUCCESS(
            f"Si todo se cobró en la cuenta de Cande → Cande le debe pasar a Cami: {a_cami:.2f} €"
        ))
        if SIN_ASIGNAR in totales:
            self.stdout.write(self.style.WARNING(
                f"OJO: {totales[SIN_ASIGNAR]:.2f} € sin profesora clara (SIN ASIGNAR) — "
                "revisalos a mano, no están sumados a Cami ni a Cande."
            ))
