"""
Generate invoices for Pago records that have no linked Documento.
Runs automatically in the Railway release phase after seed_emisores.

Usage:
    python manage.py fix_missing_invoices            # generate + report
    python manage.py fix_missing_invoices --dry-run  # report only
"""
from datetime import date

from django.core.management.base import BaseCommand

from modules.documentos.models import Documento, Emisor
from modules.documentos.invoice_service import generate_invoice_for_pago
from modules.pagos.models import Pago
from modules.pagos.constants import METODOS_FACTURA


class Command(BaseCommand):
    help = "Generate invoices for pagos that have no documento"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be done without uploading",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        prefix = "[DRY RUN] " if dry else ""

        pago_ids_with_doc = set(
            Documento.objects.exclude(pago=None).values_list("pago_id", flat=True)
        )
        missing = (
            Pago.objects.exclude(id__in=pago_ids_with_doc)
            .select_related("pagador", "alumno", "grupo", "emisor", "academia")
            .order_by("id")
        )

        count = missing.count()
        self.stdout.write(f"{prefix}Found {count} pago(s) with no documento.\n")
        if not count:
            return

        ok = skipped = errors = 0

        for pago in missing:
            emisor = pago.emisor
            if emisor is None:
                emisor = Emisor.objects.filter(
                    academia=pago.academia, slug="camiandco"
                ).first()
                if emisor and not dry:
                    pago.emisor = emisor
                    pago.save(update_fields=["emisor"])

            if emisor is None:
                self.stdout.write(f"  SKIP pago {pago.id}: no emisor")
                skipped += 1
                continue

            if not emisor.drive_folder_id:
                self.stdout.write(f"  SKIP pago {pago.id}: emisor has no drive_folder_id")
                skipped += 1
                continue

            metodo = (pago.metodo or "").lower()
            tipo   = "factura" if metodo in METODOS_FACTURA else "recibo"

            try:
                if dry:
                    self.stdout.write(
                        f"  would generate {tipo} for pago {pago.id} "
                        f"({pago.alumno.nombre if pago.alumno else '?'}, {pago.periodo})"
                    )
                    ok += 1
                    continue

                num_doc, drive_id = generate_invoice_for_pago(pago, tipo)
                Documento.objects.create(
                    academia   = pago.academia,
                    pago       = pago,
                    tipo       = tipo,
                    nombre     = f"{num_doc}.pdf",
                    num_doc    = num_doc,
                    s3_key     = drive_id,
                    local_path = "",
                    mime_type  = "application/pdf",
                )
                pago.num_doc = num_doc
                pago.save(update_fields=["num_doc"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  OK pago {pago.id}: {num_doc} → {drive_id[:24]}..."
                    )
                )
                ok += 1

            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  FAIL pago {pago.id}: {exc}"))
                errors += 1

        self.stdout.write(
            f"\n{prefix}Done — generated={ok}, skipped={skipped}, errors={errors}"
        )
