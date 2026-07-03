"""
Adds (or repairs in place) the "Contactos" tab in the Rangers Academy
Google Sheet — this is the tab modules/crm/sheets_service.py appends a
row to every time a new CRM lead is created.

Run once:
    venv/Scripts/python.exe add_contactos_sheet.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from googleapiclient.discovery import build
from modules.documentos.invoice_service import _credentials

SPREADSHEET_ID = "1pXh-ad0QYrCFvCTB6s-hVB0AdxKFYC745YZFEY53qZ4"
TAB_TITLE = "Contactos"

COLUMNS = [
    "fecha", "nombre_padre_madre", "nombre_alumno", "telefono", "email",
    "edad_alumno", "curso_escolar", "objetivo", "origen", "etapa_crm", "notas",
    "es_adulto",
]

OBJETIVO_OPTIONS = ["General", "Cambridge", "IB", "Adultos"]
ORIGEN_OPTIONS = ["Teléfono", "WhatsApp", "Instagram", "Facebook", "Recomendación", "Web"]
ETAPA_OPTIONS = [
    "nueva_consulta", "pendiente_llamar", "en_conversacion",
    "clase_prueba", "matriculado", "frio", "archivado",
]

DATA_START_ROW = 2       # 1-indexed; row 1 is the header
DATA_END_ROW = 1000

TEXT_FORMAT_COLUMNS = ["fecha", "telefono"]


def _col_index(name):
    return COLUMNS.index(name)


def get_or_create_tab(sheets):
    meta = sheets.spreadsheets().get(spreadsheetId=SPREADSHEET_ID, fields="sheets.properties").execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == TAB_TITLE:
            return s["properties"]["sheetId"], False
    resp = sheets.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={
        "requests": [{
            "addSheet": {
                "properties": {
                    "title": TAB_TITLE,
                    "gridProperties": {"frozenRowCount": 1, "columnCount": len(COLUMNS)},
                }
            }
        }]
    }).execute()
    return resp["replies"][0]["addSheet"]["properties"]["sheetId"], True


def main():
    creds = _credentials()
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    sheet_id, created = get_or_create_tab(sheets)

    # Defensively unmerge any leftover merges in row 1 (e.g. from duplicating
    # another tab) — a merge over cells in a values().update() range silently
    # swallows all but the top-left value.
    unmerge_requests = [
        {"unmergeCells": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                                     "startColumnIndex": 0, "endColumnIndex": len(COLUMNS)}}}
    ]
    sheets.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": unmerge_requests}).execute()

    sheets.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID, range=f"{TAB_TITLE}!A1",
        valueInputOption="RAW", body={"values": [COLUMNS]},
    ).execute()

    requests = [{
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": len(COLUMNS)},
            "cell": {"userEnteredFormat": {
                "backgroundColor": {"red": 0.20, "green": 0.45, "blue": 0.80},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    }]

    def data_validation(col_name, options):
        idx = _col_index(col_name)
        requests.append({
            "setDataValidation": {
                "range": {"sheetId": sheet_id,
                          "startRowIndex": DATA_START_ROW - 1, "endRowIndex": DATA_END_ROW,
                          "startColumnIndex": idx, "endColumnIndex": idx + 1},
                "rule": {
                    "condition": {"type": "ONE_OF_LIST",
                                  "values": [{"userEnteredValue": v} for v in options]},
                    "showCustomUi": True,
                    "strict": False,
                },
            }
        })

    data_validation("objetivo", OBJETIVO_OPTIONS)
    data_validation("origen", ORIGEN_OPTIONS)
    data_validation("etapa_crm", ETAPA_OPTIONS)
    data_validation("es_adulto", ["Sí", "No"])

    for col_name in TEXT_FORMAT_COLUMNS:
        idx = _col_index(col_name)
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id,
                          "startRowIndex": DATA_START_ROW - 1, "endRowIndex": DATA_END_ROW,
                          "startColumnIndex": idx, "endColumnIndex": idx + 1},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": "TEXT"}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        })

    sheets.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": requests}).execute()

    print(f"{'Created' if created else 'Repaired'} the Contactos tab.")
    print(f"URL: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")


if __name__ == "__main__":
    main()
