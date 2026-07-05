"""Bulk-import draft Pago rows from a TaxFix/Bizum reconciliation CSV.

Creates one Pago per row with alumno/pagador/grupo left blank and
estado_carga="pendiente_completar" — each row is completed later by hand
through the normal Pagos UI (selecting alumno/pagador/grupo), at which point
the reserved invoice number in numero_factura_reservado is consumed instead
of a new one being allocated.

CSV columns expected: fecha_pago, concepto_original, monto, metodo_pago,
invoice_num_asignado

Usage:
    python manage.py import_pagos_taxfix path/to/file.csv
    python manage.py import_pagos_taxfix path/to/file.csv --dry-run
"""
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from modules.documentos.models import Emisor
from modules.pagos.models import Pago

User = get_user_model()

MARCA_BY_EMISOR_SLUG = {"camiandco": "cami_and_co", "rangers": "rangers_academy"}


def _parse_fecha(raw: str):
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"fecha irreconocible: {raw!r}")


def _match_emisor(num_asignado: str, emisores):
    """Infer the Emisor + tipo (factura/recibo) from the reserved number's prefix."""
    prefix = "".join(ch for ch in num_asignado if ch.isalpha())
    for e in emisores:
        if prefix == e.factura_prefix:
            return e, "factura"
        if prefix == e.recibo_prefix:
            return e, "recibo"
    return None, None


class Command(BaseCommand):
    help = "Bulk-import draft Pago rows from a TaxFix/Bizum CSV (estado_carga=pendiente_completar)"

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--dry-run", action="store_true", help="Report what would be created without writing")

    def handle(self, *args, **options):
        path = options["csv_path"]
        dry  = options["dry_run"]
        prefix_log = "[DRY RUN] " if dry else ""

        user = User.objects.first()
        if not user:
            raise CommandError("No hay usuarios en la base de datos.")

        emisores = list(Emisor.objects.filter(academia=user))

        created = skipped = errors = 0

        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=2):  # row 1 is the header
                num_asignado = (row.get("invoice_num_asignado") or "").strip()

                try:
                    fecha    = _parse_fecha(row["fecha_pago"])
                    monto    = Decimal(str(row["monto"]).strip().replace(",", "."))
                    metodo   = (row.get("metodo_pago") or "").strip().lower()
                    concepto = (row.get("concepto_original") or "").strip()
                except (KeyError, InvalidOperation, ValueError) as e:
                    self.stdout.write(self.style.ERROR(f"  fila {i}: SKIP — {e}"))
                    errors += 1
                    continue

                if num_asignado and Pago.objects.filter(
                    academia=user, numero_factura_reservado=num_asignado
                ).exists():
                    self.stdout.write(f"  fila {i}: SKIP — {num_asignado} ya importado")
                    skipped += 1
                    continue

                emisor, tipo = _match_emisor(num_asignado, emisores) if num_asignado else (None, None)
                marca = MARCA_BY_EMISOR_SLUG.get(getattr(emisor, "slug", ""), "rangers_academy")

                self.stdout.write(
                    f"  fila {i}: {fecha} {monto}€ {metodo} num={num_asignado or '?'} "
                    f"({tipo or '?'}) emisor={getattr(emisor, 'slug', '?')} — {concepto!r}"
                )

                if dry:
                    created += 1
                    continue

                Pago.objects.create(
                    academia=user, emisor=emisor, marca=marca,
                    alumno=None, pagador=None, grupo=None,
                    periodo=fecha.strftime("%Y-%m"), fecha=fecha,
                    mensualidad=0, descuento=0, extras=[], total=monto,
                    metodo=metodo, estado="pagado",
                    concepto_original=concepto, notas=f"[import taxfix] {concepto}",
                    numero_factura_reservado=num_asignado,
                    estado_carga="pendiente_completar",
                )
                created += 1

        self.stdout.write(f"\n{prefix_log}Hecho — creados={created}, saltados={skipped}, errores={errors}")
