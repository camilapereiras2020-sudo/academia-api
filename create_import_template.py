"""
Creates (or repairs in place) the Google Sheet template used by
import_from_sheets.py.

One tab ("Alumnos"), one row per student, columns grouped by entity
(ALUMNO / PAGADOR / GRUPO) so a single row carries everything needed to
create — or match — the student's pagador and grupo.

Create a new sheet:
    venv/Scripts/python.exe create_import_template.py

Re-apply headers/formatting/validation to an existing sheet (e.g. after
changing COLUMNS below) without touching any data rows:
    venv/Scripts/python.exe create_import_template.py --sheet-id ID
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from googleapiclient.discovery import build
from modules.documentos.invoice_service import _credentials

# "Rangers-Invoice" folder in Drive — root Drive folder for Rangers Academy documents
# (Emisor.drive_folder_id for the "rangers" emisor; also holds the generated invoice PDFs).
RANGERS_FOLDER_ID = "17xDVHjzwsvaRIVhSiNAVLlFeNF-d7tF-"

SHEET_TITLE = "Rangers Academy — Importación de alumnos"
TAB_TITLE = "Alumnos"

# (header, section) — order defines the sheet's column order, A onward.
COLUMNS = [
    ("nombre_alumno",     "ALUMNO"),
    ("apellido_alumno",   "ALUMNO"),
    ("fecha_nacimiento",  "ALUMNO"),
    ("dni_alumno",        "ALUMNO"),
    ("telefono_alumno",   "ALUMNO"),
    ("email_alumno",      "ALUMNO"),
    ("nivel",             "ALUMNO"),
    ("aviso_cumple_dias", "ALUMNO"),
    ("notas_alumno",      "ALUMNO"),
    ("nombre_pagador",    "PAGADOR"),
    ("nif_pagador",       "PAGADOR"),
    ("telefono_pagador",  "PAGADOR"),
    ("email_pagador",     "PAGADOR"),
    ("metodo_pago",       "PAGADOR"),
    ("frecuencia",        "PAGADOR"),
    ("iban_pagador",      "PAGADOR"),
    ("notas_pagador",     "PAGADOR"),
    ("nombre_grupo",      "GRUPO"),
    ("nivel_grupo",       "GRUPO"),
    ("tarifa_mensual",    "GRUPO"),
    ("aula",              "GRUPO"),
    ("horario",           "GRUPO"),
]

SECTION_COLORS = {
    "ALUMNO":  {"dark": (0.20, 0.45, 0.80), "light": (0.85, 0.91, 0.98)},
    "PAGADOR": {"dark": (0.16, 0.55, 0.35), "light": (0.87, 0.95, 0.87)},
    "GRUPO":   {"dark": (0.80, 0.45, 0.10), "light": (0.99, 0.90, 0.78)},
}

# Rows of manually-entered data start here (1-indexed); rows 1-2 are headers.
DATA_START_ROW = 3       # 1-indexed
DATA_END_ROW = 1000      # generous room for future entries

NIVEL_OPTIONS = ["A1", "A2", "B1", "B2", "C1"]
METODO_OPTIONS = ["efectivo", "bizum", "transferencia", "domiciliacion", "tarjeta"]
FRECUENCIA_OPTIONS = ["mensual", "por_clase", "trimestral", "anual"]

TEXT_FORMAT_COLUMNS = ["fecha_nacimiento", "telefono_alumno", "telefono_pagador", "iban_pagador"]

NOTES = {
    "fecha_nacimiento": "Formato: DD/MM/AAAA. Escribe 8 dígitos (ej. 13042007) y el script de la "
                         "hoja lo convierte solo a 13/04/2007.",
    "aviso_cumple_dias": "Nº de días antes del cumpleaños para avisar. Déjalo en blanco si no aplica.",
    "horario": "Ej: Lun/Mié 17:30-18:30  (días separados por /, varios bloques separados por coma)",
}


def _color(rgb):
    r, g, b = rgb
    return {"red": r, "green": g, "blue": b}


def _section_ranges():
    """Yield (section, startIndex, endIndex) column ranges in COLUMNS order."""
    start = 0
    current = COLUMNS[0][1]
    for i, (_, section) in enumerate(COLUMNS):
        if section != current:
            yield current, start, i
            start, current = i, section
    yield current, start, len(COLUMNS)


def _col_index(name):
    return next(i for i, (n, _) in enumerate(COLUMNS) if n == name)


def build_header_rows():
    n_cols = len(COLUMNS)
    row1 = [""] * n_cols
    for section, start, _end in _section_ranges():
        row1[start] = section
    row2 = [name for name, _ in COLUMNS]
    return row1, row2


def build_format_requests(sheet_id):
    requests = []

    for section, start, end in _section_ranges():
        colors = SECTION_COLORS[section]
        requests.append({
            "mergeCells": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                          "startColumnIndex": start, "endColumnIndex": end},
                "mergeType": "MERGE_ALL",
            }
        })
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                          "startColumnIndex": start, "endColumnIndex": end},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": _color(colors["dark"]),
                    "horizontalAlignment": "CENTER",
                    "textFormat": {"bold": True, "foregroundColor": _color((1, 1, 1))},
                }},
                "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)",
            }
        })
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2,
                          "startColumnIndex": start, "endColumnIndex": end},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": _color(colors["light"]),
                    "textFormat": {"bold": True},
                }},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        })

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

    data_validation("nivel", NIVEL_OPTIONS)
    data_validation("metodo_pago", METODO_OPTIONS)
    data_validation("frecuencia", FRECUENCIA_OPTIONS)

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

    for col_name, note in NOTES.items():
        idx = _col_index(col_name)
        requests.append({
            "updateCells": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2,
                          "startColumnIndex": idx, "endColumnIndex": idx + 1},
                "rows": [{"values": [{"note": note}]}],
                "fields": "note",
            }
        })

    return requests


def apply_template(sheets, spreadsheet_id, sheet_id):
    """Write headers + formatting/validation to an existing sheet/tab. Data rows untouched."""
    n_cols = len(COLUMNS)
    requests = [{
        "updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"columnCount": n_cols}},
            "fields": "gridProperties.columnCount",
        }
    }]
    requests += build_format_requests(sheet_id)
    sheets.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()

    row1, row2 = build_header_rows()
    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=f"{TAB_TITLE}!A1",
        valueInputOption="RAW", body={"values": [row1, row2]},
    ).execute()


def create_new(sheets, drive):
    n_cols = len(COLUMNS)
    create_body = {
        "properties": {"title": SHEET_TITLE},
        "sheets": [{
            "properties": {
                "title": TAB_TITLE,
                "gridProperties": {"frozenRowCount": 2, "columnCount": n_cols},
            }
        }],
    }
    created = sheets.spreadsheets().create(
        body=create_body, fields="spreadsheetId,sheets.properties.sheetId"
    ).execute()
    spreadsheet_id = created["spreadsheetId"]
    sheet_id = created["sheets"][0]["properties"]["sheetId"]

    apply_template(sheets, spreadsheet_id, sheet_id)

    file = drive.files().get(fileId=spreadsheet_id, fields="parents").execute()
    prev_parents = ",".join(file.get("parents", []))
    drive.files().update(
        fileId=spreadsheet_id, addParents=RANGERS_FOLDER_ID,
        removeParents=prev_parents, fields="id,parents",
    ).execute()
    return spreadsheet_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet-id", help="Repair an existing spreadsheet instead of creating a new one")
    args = parser.parse_args()

    creds = _credentials()
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    if args.sheet_id:
        meta = sheets.spreadsheets().get(
            spreadsheetId=args.sheet_id, fields="sheets.properties"
        ).execute()
        tab = next(s for s in meta["sheets"] if s["properties"]["title"] == TAB_TITLE)
        apply_template(sheets, args.sheet_id, tab["properties"]["sheetId"])
        spreadsheet_id = args.sheet_id
        print("Repaired existing sheet (data rows untouched).")
    else:
        spreadsheet_id = create_new(sheets, drive)
        print(f"Created: {SHEET_TITLE}")

    print(f"Spreadsheet ID: {spreadsheet_id}")
    print(f"URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")


if __name__ == "__main__":
    main()
