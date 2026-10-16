"""Listado de cobros del mes por pagador, con a qué profesora (Cande / Cami)
corresponde cada alumno y cuánto le toca a cada una.

Pensado para el caso "todo se cobró en la cuenta de Cande": muestra cuánto
tiene que pasarle Cande a Cami (lo que corresponde a los alumnos de Cami).

Solo lectura — no crea ni modifica nada.

La profesora de cada pago sale del grupo del pago (Pago.grupo.profesor); si el
pago no tiene grupo, de los grupos del alumno — y solo si todos son de la
misma profesora. Lo que no se pueda asignar con certeza queda aparte, en
"SIN ASIGNAR", para revisarlo a mano: nunca se adivina.

Dos modos:
- (por defecto) lo REGISTRADO: pagos del período en estado "pagado".
- --calculado: lo que CORRESPONDE cobrar según las tarifas, con la misma
  cuenta que la ficha del alumno y la Calculadora de pagadores
  (calcular_cuota_alumno: cuota manual > Bono Familia > tarifa de clase),
  haya o no pagos cargados. Si un alumno tiene clases con las dos
  profesoras, su cuota se reparte por horas (método de mayores restos, al
  céntimo). Ranger Express va aparte: no se atribuye a ninguna profesora.

Uso:
    python manage.py reparto_cobros
    python manage.py reparto_cobros --periodo 2026-10 --incluir-pendientes
    python manage.py reparto_cobros --periodo 2026-10 --calculado
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


RANGER_EXPRESS = "RANGER EXPRESS (aparte)"


def _repartir_exacto(pesos, total):
    """Reparte `total` en proporción a `pesos` ({clave: Decimal}) por el método
    de mayores restos: trunca a céntimos y reparte los céntimos que faltan de
    a uno, así la suma cuadra EXACTAMENTE con `total`."""
    from decimal import ROUND_DOWN

    cent = Decimal("0.01")
    base = sum(pesos.values(), Decimal("0"))
    exactos = {k: total * v / base for k, v in pesos.items()}
    partes = {k: v.quantize(cent, rounding=ROUND_DOWN) for k, v in exactos.items()}
    faltan = int(((total - sum(partes.values(), Decimal("0"))) / cent).to_integral_value())
    for k in sorted(exactos, key=lambda k: exactos[k] - partes[k], reverse=True)[:faltan]:
        partes[k] += cent
    return partes


def calcular_esperado(owner, periodo):
    """Lo que corresponde cobrar según tarifas, por pagador y profesora.

    Devuelve (por_pagador, totales, avisos, estados):
      por_pagador: {pagador: [(alumno, profesora, importe), ...]}
      totales: {profesora: Decimal}
      avisos: [str] — alumnos sin cuota calculable (hay que mirarlos a mano)
      estados: {pagador: "pagado" | "parcial" | "pendiente" | "sin_generar"}
    """
    from decimal import ROUND_HALF_UP
    from modules.alumnos.models import Alumno
    from modules.pagos.models import Pago
    from modules.tarifas.pricing import calcular_cuota_alumno

    alumnos = list(
        Alumno.objects.filter(academia=owner, activo=True)
        .select_related("pagador")
        .prefetch_related("inscripciones__grupo__profesor", "pagador__alumnos")
    )
    pagos = defaultdict(list)
    for pg in Pago.objects.filter(academia=owner, periodo=periodo).exclude(estado="anulado"):
        pagos[pg.alumno_id].append(pg.estado)

    por_pagador = defaultdict(list)
    totales = defaultdict(lambda: Decimal("0"))
    avisos = []
    estados_por_pagador = defaultdict(list)

    for a in alumnos:
        pagador = a.pagador.nombre if a.pagador_id else "(sin pagador)"
        if a.es_adulto:
            avisos.append(f"{a.nombre}: adulto, se cobra por hora — calcular a mano.")
            continue
        info = calcular_cuota_alumno(a)
        for av in info["avisos"]:
            avisos.append(f"{a.nombre}: {av}")
        estados_por_pagador[pagador].extend(pagos.get(a.id, []) or ["sin_generar"])

        if info["cuota"] is not None:
            cuota = Decimal(str(info["cuota"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            horas = defaultdict(int)
            for i in a.inscripciones.all():
                if i.grupo and i.grupo.profesor_id:
                    horas[i.grupo.profesor.nombre] += len(i.grupo.horarios or []) or 1
            if len(horas) == 1:
                reparto = {next(iter(horas)): cuota}
            elif len(horas) > 1:
                reparto = _repartir_exacto({k: Decimal(v) for k, v in horas.items()}, cuota)
            else:
                reparto = {SIN_ASIGNAR: cuota}
            for profesora, importe in reparto.items():
                por_pagador[pagador].append((a.nombre, profesora, importe))
                totales[profesora] += importe
        if info.get("ranger_express") is not None:
            importe = Decimal(str(info["ranger_express"]))
            por_pagador[pagador].append((a.nombre, RANGER_EXPRESS, importe))
            totales[RANGER_EXPRESS] += importe

    estados = {}
    for pagador, lista in estados_por_pagador.items():
        if all(e == "pagado" for e in lista):
            estados[pagador] = "pagado"
        elif any(e in ("pagado", "parcial") for e in lista):
            estados[pagador] = "parcial"
        elif all(e == "sin_generar" for e in lista):
            estados[pagador] = "sin_generar"
        else:
            estados[pagador] = "pendiente"
    return dict(por_pagador), dict(totales), avisos, estados


class Command(BaseCommand):
    help = "Cobros del mes por pagador y reparto entre Cande y Cami."

    def add_arguments(self, parser):
        parser.add_argument("--periodo", default=None, help="AAAA-MM (por defecto, el mes actual).")
        parser.add_argument(
            "--incluir-pendientes", action="store_true",
            help="Incluir también pagos pendientes/parciales (por defecto, solo los pagados).",
        )
        parser.add_argument(
            "--calculado", action="store_true",
            help="Usar lo que corresponde cobrar según tarifas, no solo lo registrado como pagado.",
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
        avisos, estados = [], {}
        if options["calculado"]:
            por_pagador, totales, avisos, estados = calcular_esperado(owner, periodo)
            estado = "calculado según tarifas"
        else:
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
            marca_estado = f"  [{estados[pagador]}]" if pagador in estados else ""
            self.stdout.write(f"{pagador}  —  total {total_pagador:.2f} €{marca_estado}")
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
        for aviso in avisos:
            self.stdout.write(self.style.WARNING(f"  ! {aviso}"))
        if avisos:
            self.stdout.write(f"({len(avisos)} aviso(s): esos alumnos NO están sumados arriba.)")
        if RANGER_EXPRESS in totales:
            self.stdout.write(
                f"Ranger Express: {totales[RANGER_EXPRESS]:.2f} € van aparte (no sumados a Cami ni a Cande)."
            )
        if SIN_ASIGNAR in totales:
            self.stdout.write(self.style.WARNING(
                f"OJO: {totales[SIN_ASIGNAR]:.2f} € sin profesora clara (SIN ASIGNAR) — "
                "revisalos a mano, no están sumados a Cami ni a Cande."
            ))
