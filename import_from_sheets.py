"""
Bulk-imports alumnos (+ their pagador and grupo) from the Google Sheet
created by create_import_template.py, via the platform API.

For each data row:
  - matches/creates the pagador by nombre_pagador
  - matches/creates the grupo by nombre_grupo
  - if an alumno with the same nombre_alumno (nombre + apellido) already
    exists, it is UPDATED: telefono, email, nivel, pagador, and grupo are
    patched to the sheet's values, but only the fields that actually
    changed, and only when the sheet cell is non-empty (a blank cell
    never clears existing data — it just means "no update for this field")
  - otherwise the alumno is created as before

Usage:
    venv/Scripts/python.exe import_from_sheets.py [--sheet-id ID] [--dry-run]

Prompts for the platform superuser email/password interactively.
"""
import argparse
import getpass
import os
import re
import sys
import unicodedata

import requests
from googleapiclient.discovery import build

sys.path.insert(0, os.path.dirname(__file__))
from modules.documentos.invoice_service import _credentials

DEFAULT_SPREADSHEET_ID = "1pXh-ad0QYrCFvCTB6s-hVB0AdxKFYC745YZFEY53qZ4"  # "Rangers Academy — Importación de alumnos"
TAB_TITLE = "Alumnos"
DATA_RANGE = f"{TAB_TITLE}!A3:V"

API_BASE = "https://academia-api-production-db7a.up.railway.app/api/v1/"

# column order must match create_import_template.py's COLUMNS list
COL_NOMBRE_ALUMNO, COL_APELLIDO_ALUMNO, COL_FECHA_NAC, COL_DNI_ALUMNO, COL_TEL_ALUMNO, \
    COL_EMAIL_ALUMNO, COL_NIVEL, COL_AVISO_CUMPLE, COL_NOTAS_ALUMNO, COL_NOMBRE_PAGADOR, \
    COL_NIF_PAGADOR, COL_TEL_PAGADOR, COL_EMAIL_PAGADOR, COL_METODO, COL_FRECUENCIA, \
    COL_IBAN, COL_NOTAS_PAGADOR, COL_NOMBRE_GRUPO, COL_NIVEL_GRUPO, COL_TARIFA, COL_AULA, \
    COL_HORARIO = range(22)

DIA_MAP = {"lun": 0, "mar": 1, "mie": 2, "jue": 3, "vie": 4, "sab": 5}
HORARIO_BLOCK_RE = re.compile(r"^(.+?)\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$")


def _cell(row, idx):
    return row[idx].strip() if idx < len(row) and row[idx] else ""


def _norm(s):
    return s.strip().lower()


def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def parse_fecha(text):
    """DD/MM/YYYY -> YYYY-MM-DD, or None."""
    if not text:
        return None
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if not m:
        return None
    d, mth, y = m.groups()
    return f"{y}-{int(mth):02d}-{int(d):02d}"


def parse_horario(text):
    """'Lun/Mié 17:30-18:30' (comma-separated blocks) -> [{"dia":0,"ini":"17:30","fin":"18:30"}, ...]"""
    if not text:
        return []
    horarios = []
    for block in text.split(","):
        block = block.strip()
        if not block:
            continue
        m = HORARIO_BLOCK_RE.match(block)
        if not m:
            continue
        days_str, ini, fin = m.groups()
        for d in days_str.split("/"):
            key = _strip_accents(d.strip().lower())[:3]
            dia = DIA_MAP.get(key)
            if dia is not None:
                horarios.append({"dia": dia, "ini": ini, "fin": fin})
    return horarios


class ApiClient:
    def __init__(self, base_url, access_token):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {access_token}"

    def get(self, path):
        r = self.session.get(self.base_url + path)
        r.raise_for_status()
        return r.json()

    def post(self, path, payload):
        r = self.session.post(self.base_url + path, json=payload)
        r.raise_for_status()
        return r.json()

    def patch(self, path, payload):
        r = self.session.patch(self.base_url + path, json=payload)
        r.raise_for_status()
        return r.json()


def login(base_url, email, password):
    r = requests.post(base_url + "auth/login/", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access"]


def read_sheet_rows(spreadsheet_id):
    creds = _credentials()
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    result = sheets.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=DATA_RANGE
    ).execute()
    return result.get("values", [])


def build_name_index(records):
    return {_norm(r["nombre"]): r["id"] for r in records}


def build_full_index(records):
    return {_norm(r["nombre"]): r for r in records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet-id", default=DEFAULT_SPREADSHEET_ID, help="Google Sheet spreadsheet ID")
    parser.add_argument("--api-base", default=API_BASE, help="Platform API base URL")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without calling the API")
    parser.add_argument("--row", type=int, help="Only import this one sheet row (1-indexed, e.g. 3 for the first data row)")
    args = parser.parse_args()

    if not args.sheet_id:
        print("No spreadsheet ID given. Pass --sheet-id or set DEFAULT_SPREADSHEET_ID.")
        sys.exit(1)

    rows = read_sheet_rows(args.sheet_id)
    if not rows:
        print("Sheet has no data rows.")
        return
    if args.row:
        offset = args.row - 3
        if offset < 0 or offset >= len(rows):
            print(f"Row {args.row} is out of range.")
            sys.exit(1)
        rows = [rows[offset]]

    email = input("Platform email: ").strip()
    password = getpass.getpass("Platform password: ")
    try:
        access = login(args.api_base, email, password)
    except requests.HTTPError as e:
        print(f"Login failed: {e}")
        sys.exit(1)
    api = ApiClient(args.api_base, access)

    pagadores_idx = build_name_index(api.get("pagadores/"))
    grupos_idx = build_name_index(api.get("grupos/"))
    alumnos_full = build_full_index(api.get("alumnos/"))

    created, updated, unchanged, errors = 0, 0, 0, []

    for i, row in enumerate(rows, start=args.row or 3):  # 1-indexed sheet row number, data starts at row 3
        nombre_pila = _cell(row, COL_NOMBRE_ALUMNO)
        if not nombre_pila:
            continue  # blank row
        apellido_alumno = _cell(row, COL_APELLIDO_ALUMNO)
        nombre_alumno = f"{nombre_pila} {apellido_alumno}".strip()

        try:
            existing = alumnos_full.get(_norm(nombre_alumno))

            pagador_id = None
            nombre_pagador = _cell(row, COL_NOMBRE_PAGADOR)
            if nombre_pagador:
                key = _norm(nombre_pagador)
                pagador_id = pagadores_idx.get(key)
                if pagador_id is None:
                    if not args.dry_run:
                        pagador = api.post("pagadores/", {
                            "nombre": nombre_pagador,
                            "nif": _cell(row, COL_NIF_PAGADOR),
                            "telefono": _cell(row, COL_TEL_PAGADOR),
                            "email": _cell(row, COL_EMAIL_PAGADOR),
                            "metodo": _cell(row, COL_METODO),
                            "frecuencia": _cell(row, COL_FRECUENCIA),
                            "iban": _cell(row, COL_IBAN),
                            "notas": _cell(row, COL_NOTAS_PAGADOR),
                        })
                        pagador_id = pagador["id"]
                    pagadores_idx[key] = pagador_id

            grupo_id = None
            nombre_grupo = _cell(row, COL_NOMBRE_GRUPO)
            if nombre_grupo:
                key = _norm(nombre_grupo)
                grupo_id = grupos_idx.get(key)
                if grupo_id is None:
                    tarifa = _cell(row, COL_TARIFA)
                    if not args.dry_run:
                        grupo = api.post("grupos/", {
                            "nombre": nombre_grupo,
                            "nivel": _cell(row, COL_NIVEL_GRUPO),
                            "tarifa": tarifa or "0",
                            "aula": _cell(row, COL_AULA),
                            "horarios": parse_horario(_cell(row, COL_HORARIO)),
                        })
                        grupo_id = grupo["id"]
                    grupos_idx[key] = grupo_id

            if existing is not None:
                # Update path: only patch fields that are non-empty in the
                # sheet AND differ from the alumno's current value. A blank
                # sheet cell never clears existing data.
                patch_fields = {}
                telefono = _cell(row, COL_TEL_ALUMNO)
                if telefono and telefono != (existing.get("telefono") or ""):
                    patch_fields["telefono"] = telefono
                email = _cell(row, COL_EMAIL_ALUMNO)
                if email and email != (existing.get("email") or ""):
                    patch_fields["email"] = email
                nivel = _cell(row, COL_NIVEL)
                if nivel and nivel != (existing.get("nivel") or ""):
                    patch_fields["nivel"] = nivel
                if pagador_id is not None and pagador_id != existing.get("pagador"):
                    patch_fields["pagador"] = pagador_id
                if grupo_id is not None and grupo_id != existing.get("grupo"):
                    patch_fields["grupo"] = grupo_id

                if patch_fields:
                    if not args.dry_run:
                        api.patch(f"alumnos/{existing['id']}/", patch_fields)
                    updated += 1
                else:
                    unchanged += 1
                continue

            aviso = _cell(row, COL_AVISO_CUMPLE)
            if not args.dry_run:
                alumno = api.post("alumnos/", {
                    "nombre": nombre_alumno,
                    "fecha_nacimiento": parse_fecha(_cell(row, COL_FECHA_NAC)),
                    "dni": _cell(row, COL_DNI_ALUMNO),
                    "telefono": _cell(row, COL_TEL_ALUMNO),
                    "email": _cell(row, COL_EMAIL_ALUMNO),
                    "nivel": _cell(row, COL_NIVEL),
                    "aviso_cumple_dias": int(aviso) if aviso.isdigit() else None,
                    "notas": _cell(row, COL_NOTAS_ALUMNO),
                    "pagador": pagador_id,
                    "grupo": grupo_id,
                })
                alumnos_full[_norm(nombre_alumno)] = alumno
            else:
                alumnos_full[_norm(nombre_alumno)] = {"id": -1}
            created += 1

        except requests.HTTPError as e:
            errors.append(f"Fila {i} ({nombre_alumno}): {e.response.status_code} {e.response.text[:200]}")
        except Exception as e:
            errors.append(f"Fila {i} ({nombre_alumno}): {e}")

    print(f"\n{created} creados, {updated} actualizados, {unchanged} sin cambios, {len(errors)} errores")
    for err in errors:
        print(f"  ✗ {err}")


if __name__ == "__main__":
    main()
