"""Logs invoice/receipt issuance and voiding to the Facturas/Recibos Google Sheet
registry (separate from the Drive PDF storage) — kept so pending/totals
calculations can exclude anulada documents as real income.
"""
from googleapiclient.discovery import build

from .invoice_service import _credentials

SPREADSHEET_ID = "1X--yaqqs9GgsbG-gA03HS42qCpspc9l_y8kZiV0ooKs"


def _tab_for(tipo: str) -> str:
    return "Facturas" if tipo == "factura" else "Recibos"


def _sheets():
    return build("sheets", "v4", credentials=_credentials(), cache_discovery=False)


def log_emision(documento) -> None:
    pago = documento.pago
    tab  = _tab_for(documento.tipo)
    row = [
        documento.emitida_at.strftime("%d/%m/%Y") if documento.emitida_at else "",
        documento.num_doc,
        pago.alumno.nombre if pago and pago.alumno else "",
        pago.pagador.nombre if pago and pago.pagador else "",
        pago.periodo if pago else "",
        str(pago.total) if pago else "",
        pago.metodo if pago else "",
        "Emitida",
        "",
        "",
    ]
    _sheets().spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range=f"{tab}!A1",
        valueInputOption="RAW", insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


def log_anulacion(documento) -> None:
    tab     = _tab_for(documento.tipo)
    service = _sheets()

    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f"{tab}!B2:B10000",
    ).execute()

    row_index = None
    for i, r in enumerate(result.get("values", [])):
        if r and r[0] == documento.num_doc:
            row_index = i + 2  # +1 for 1-index, +1 for header row
            break

    if row_index is None:
        # Never logged in the first place (e.g. a legacy doc predating this
        # feature) — append a row now rather than losing the void event.
        log_emision(documento)
        return

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=f"{tab}!H{row_index}:J{row_index}",
        valueInputOption="RAW",
        body={"values": [[
            "Anulada",
            documento.motivo_anulacion,
            documento.anulada_at.strftime("%d/%m/%Y %H:%M") if documento.anulada_at else "",
        ]]},
    ).execute()
