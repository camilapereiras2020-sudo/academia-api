"""Appends a row to the "Contactos" Google Sheet tab whenever a CRM lead is created."""
from googleapiclient.discovery import build

from modules.documentos.invoice_service import _credentials

SPREADSHEET_ID = "1pXh-ad0QYrCFvCTB6s-hVB0AdxKFYC745YZFEY53qZ4"
TAB_TITLE = "Contactos"


def append_contacto_row(lead):
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
