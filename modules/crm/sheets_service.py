"""Appends a row to the "Contactos" Google Sheet tab whenever a CRM lead is created."""
import os

from django.conf import settings
from googleapiclient.discovery import build

from modules.documentos.invoice_service import _credentials

SPREADSHEET_ID = os.environ.get(
    "GOOGLE_SHEETS_CONTACTOS_SPREADSHEET_ID", "1pXh-ad0QYrCFvCTB6s-hVB0AdxKFYC745YZFEY53qZ4"
)
TAB_TITLE = "Contactos"


def _block_if_untested_in_tests() -> None:
    """Same hard safety net as modules.documentos.sheets_log — this was
    missing here, so a test that creates a Lead without mocking this
    function would silently write to the real production Contactos sheet."""
    if getattr(settings, "TESTING", False):
        raise RuntimeError(
            "crm.sheets_service.append_contacto_row was called during tests without "
            "being mocked. This would write to the real production Google Sheet. "
            "Add @patch('modules.crm.sheets_service.append_contacto_row') to this test."
        )


def append_contacto_row(lead):
    _block_if_untested_in_tests()
    creds = _credentials()
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    row = [
        lead.created_at.strftime("%d/%m/%Y"),
        lead.nombre_contacto,
        lead.nombre_alumno,
        lead.telefono,
        lead.email,
        lead.edad_alumno or "",
        lead.curso_escolar,
        lead.get_objetivo_display(),
        lead.get_origen_display(),
        lead.etapa,
        lead.notas,
        "Sí" if lead.es_adulto else "No",
    ]
    sheets.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range=f"{TAB_TITLE}!A1",
        valueInputOption="RAW", insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
