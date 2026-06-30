"""
Repair Documento records that cannot be served:
  1. s3_key is empty (legacy local-path docs)
  2. s3_key is set but the Drive file returns 404 (file was deleted)

Regenerates the PDF from the linked Pago and re-uploads to Drive using
the EXISTING num_doc so invoice numbers stay unchanged.

Usage:
    python manage.py fix_legacy_docs            # fix + report
    python manage.py fix_legacy_docs --dry-run  # report only, no writes
"""
import os
from datetime import date

from django.core.management.base import BaseCommand

from modules.documentos.models import Documento
from modules.documentos.invoice_service import (
    generate_pdf_bytes, upload_to_drive, download_from_drive,
)


def _drive_file_missing(s3_key: str) -> bool:
    """Return True if the Drive file no longer exists."""
    if not s3_key:
        return True
    try:
        download_from_drive(s3_key)
        return False
    except Exception:
        return True


class Command(BaseCommand):
    help = "Re-upload Documento records with missing or broken Drive files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be done without making changes",
        )
        parser.add_argument(
            "--check-s3", action="store_true",
            help="Also verify existing s3_keys are reachable (slow — makes Drive API calls)",
        )

    def handle(self, *args, **options):
        dry      = options["dry_run"]
        check_s3 = options["check_s3"]
        prefix   = "[DRY RUN] " if dry else ""

        all_docs = Documento.objects.select_related(
            "pago__pagador", "pago__alumno", "pago__grupo", "pago__emisor",
        )

        broken = []
        for doc in all_docs:
            if not doc.s3_key:
                broken.append((doc, "no s3_key"))
            elif check_s3 and _drive_file_missing(doc.s3_key):
                broken.append((doc, f"Drive 404 for {doc.s3_key[:20]}..."))

        self.stdout.write(f"{prefix}Found {len(broken)} Documento(s) to repair.\n")
        if not broken:
            return

        fixed = skipped = errors = 0

        for doc, reason in broken:
            self.stdout.write(f"  {doc.num_doc} (id={doc.id}) — {reason}")

            pago = doc.pago
            if pago is None:
                self.stdout.write("    → SKIP: no linked Pago, cannot regenerate")
                skipped += 1
                continue

            emisor = pago.emisor
            if emisor is None:
                from modules.documentos.models import Emisor
                emisor = Emisor.objects.filter(
                    academia=pago.academia, slug="camiandco"
                ).first()
            if emisor is None:
                self.stdout.write("    → SKIP: no emisor found")
                skipped += 1
                continue

            folder_id = emisor.drive_folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
            if not folder_id:
                self.stdout.write("    → SKIP: no Drive folder configured")
                skipped += 1
                continue

            try:
                pagador = pago.pagador
                alumno  = pago.alumno
                grupo   = pago.grupo
                metodo  = pago.metodo or ""
                extras  = pago.extras or []
                fecha   = pago.fecha or date.today()

                pdf_bytes = generate_pdf_bytes(
                    academia_nombre = emisor.nombre,
                    academia_dir    = emisor.direccion or "",
                    academia_ciudad = emisor.ciudad    or "",
                    academia_tel    = emisor.telefono  or "",
                    academia_cif    = emisor.nif       or "",
                    iban            = emisor.iban      or "",
                    pagador_nombre  = pagador.nombre,
                    pagador_nif     = getattr(pagador, "nif",      "") or "",
                    pagador_tel     = getattr(pagador, "telefono", "") or "",
                    pagador_email   = getattr(pagador, "email",    "") or "",
                    alumno_nombre   = alumno.nombre if alumno else "—",
                    grupo_nombre    = grupo.nombre  if grupo  else "",
                    periodo         = pago.periodo,
                    mensualidad     = pago.mensualidad,
                    descuento       = pago.descuento,
                    extras          = extras,
                    total           = pago.total,
                    metodo          = metodo,
                    concepto_libre  = getattr(pago, "concepto_libre", "") or "",
                    num_doc         = doc.num_doc,
                    fecha           = fecha,
                    tipo            = doc.tipo,
                )

                year_str, month_str = pago.periodo.split("-")
                pdf_name = doc.nombre if doc.nombre.endswith(".pdf") else f"{doc.num_doc}.pdf"

                if dry:
                    self.stdout.write(
                        f"    → would upload {len(pdf_bytes)}b as {pdf_name!r} "
                        f"to folder {folder_id[:20]}..."
                    )
                    fixed += 1
                    continue

                file_id = upload_to_drive(
                    pdf_bytes, pdf_name, int(year_str), int(month_str), folder_id
                )
                doc.s3_key = file_id
                doc.save(update_fields=["s3_key"])
                self.stdout.write(f"    → OK: {len(pdf_bytes)}b → Drive {file_id}")
                fixed += 1

            except Exception as exc:
                self.stdout.write(f"    → ERROR: {exc}")
                errors += 1

        self.stdout.write(
            f"\n{prefix}Done — fixed={fixed}, skipped={skipped}, errors={errors}"
        )
