"""
Daily cron counterpart to the one-off export_to_sheets.py script (repo
root) — same output, but runs straight against the ORM (no HTTP login,
no interactive password prompt) so it can run unattended via Railway
Cron Job, same pattern as send_birthday_emails.

Overwrites the "Alumnos" tab's data rows (3+) every run with a fresh
snapshot of every alumno on the platform (both marcas) — headers
(rows 1-2, from create_import_template.py) are left untouched. This is a
platform -> Sheet one-way sync: editing the Sheet directly does NOT feed
back into the platform, and the next run of this command overwrites
whatever was typed there. If two-way sync is ever wanted, this and
import_from_sheets.py need to be reconciled first (see that script's
docstring) -- don't add a Sheet -> platform cron without doing that.

Column layout / simplifications: identical to export_to_sheets.py --
see that file's docstring (no separate apellido field on Alumno, only
the alphabetically-first grupo is exported per student, "marca" is an
extra 23rd column not in create_import_template.py's original layout).
"""
import logging

from django.core.management.base import BaseCommand

from modules.alumnos.models import Alumno
from modules.documentos.invoice_service import _credentials

logger = logging.getLogger(__name__)

DEFAULT_SPREADSHEET_ID = "1pXh-ad0QYrCFvCTB6s-hVB0AdxKFYC745YZFEY53qZ4"  # "Rangers Academy — Importación de alumnos"
TAB_TITLE = "Alumnos"
DIA_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]


def _fmt_fecha(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _fmt_horario(horarios):
    """Same inverse of import_from_sheets.parse_horario as export_to_sheets.py."""
    if not horarios:
        return ""
    groups = {}
    for h in horarios:
        key = (h.get("ini"), h.get("fin"))
        groups.setdefault(key, []).append(h.get("dia"))
    blocks = []
    for (ini, fin), dias in groups.items():
        dias_str = "/".join(DIA_LABELS[d] for d in sorted(dias) if d is not None and 0 <= d < 6)
        blocks.append(f"{dias_str} {ini}-{fin}")
    return ", ".join(blocks)


def _build_row(alumno):
    """Returns (row, warning_or_None). Mirrors export_to_sheets.build_row,
    but reads Inscripcion/Grupo/Pagador straight off the model instances
    (already prefetched by the caller) instead of API response dicts."""
    inscripciones = sorted(alumno.inscripciones.all(), key=lambda i: i.grupo.nombre)
    grupo = inscripciones[0].grupo if inscripciones else None
    warning = None
    if len(inscripciones) > 1:
        warning = (
            f"{alumno.nombre}: matriculado en {len(inscripciones)} grupos, "
            f"solo se exportó '{grupo.nombre}' -- revisar el resto a mano."
        )

    pagador = alumno.pagador

    row = [
        alumno.nombre or "",       # nombre_alumno
        "",                          # apellido_alumno -- not stored separately on Alumno
        _fmt_fecha(alumno.fecha_nacimiento),
        alumno.dni or "",
        alumno.telefono or "",
        alumno.email or "",
        alumno.nivel or "",
        str(alumno.aviso_cumple_dias) if alumno.aviso_cumple_dias is not None else "",
        alumno.notas or "",
        pagador.nombre if pagador else "",
        pagador.nif if pagador else "",
        pagador.telefono if pagador else "",
        pagador.email if pagador else "",
        pagador.metodo if pagador else "",
        pagador.frecuencia if pagador else "",
        pagador.iban if pagador else "",
        pagador.notas if pagador else "",
        grupo.nombre if grupo else "",
        grupo.nivel if grupo else "",
        str(grupo.tarifa) if grupo else "",
        grupo.aula if grupo else "",
        _fmt_horario(grupo.horarios) if grupo else "",
        alumno.marca or "",          # extra column, see module docstring
    ]
    return row, warning


class Command(BaseCommand):
    help = (
        "Overwrites the 'Alumnos' Google Sheet tab with a fresh snapshot of every "
        "alumno on the platform (both marcas). One-way, platform -> Sheet. Intended "
        "to run once daily via an external scheduler (Railway Cron Job)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--sheet-id", default=DEFAULT_SPREADSHEET_ID, help="Google Sheet spreadsheet ID")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be exported without writing to the Sheet.",
        )

    def handle(self, *args, **options):
        sheet_id = options["sheet_id"]
        dry_run = options["dry_run"]

        alumnos = Alumno.objects.select_related("pagador").prefetch_related(
            "inscripciones__grupo"
        ).order_by("nombre")

        rows, warnings = [], []
        for alumno in alumnos:
            row, warning = _build_row(alumno)
            rows.append(row)
            if warning:
                warnings.append(warning)

        self.stdout.write(f"{len(rows)} alumnos listos para exportar.")
        for w in warnings:
            self.stdout.write(self.style.WARNING(f"  {w}"))
            logger.warning(w)

        if dry_run:
            self.stdout.write("[dry-run] no se escribió nada en la Sheet.")
            return

        from googleapiclient.discovery import build

        creds = _credentials()
        sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

        # Clear existing data rows first so a shorter export never leaves
        # stale trailing rows from a previous (larger) run.
        sheets.spreadsheets().values().clear(
            spreadsheetId=sheet_id, range=f"{TAB_TITLE}!A3:W1000",
        ).execute()

        if rows:
            sheets.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=f"{TAB_TITLE}!A3",
                valueInputOption="RAW", body={"values": rows},
            ).execute()

        self.stdout.write(self.style.SUCCESS(f"Exportados {len(rows)} alumnos a la Sheet."))
