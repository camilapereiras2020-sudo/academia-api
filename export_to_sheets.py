"""
Reverse of import_from_sheets.py: dumps every alumno currently on the
platform (both marcas) into the "Alumnos" tab of the same Google Sheet
used for import, REPLACING whatever data rows are there now (rows 3+).
Rows 1-2 (headers/formatting from create_import_template.py) are left
untouched.

Column layout matches create_import_template.py's COLUMNS exactly, plus
one extra column at the end: "marca" (rangers_academy / cami_and_co) --
needed because a single sheet now mixes both brands, unlike
import_from_sheets.py's one-brand-per-run assumption. If this sheet is
re-imported later, import_from_sheets.py will need a small update to read
marca per-row instead of taking it from --marca; not done here since this
script is for now an export/backup only.

Known simplifications (fine for a snapshot, not perfect round-tripping):
  - Alumno has one "nombre" field, no separate apellido -- the full name
    goes in nombre_alumno, apellido_alumno is left blank.
  - A student enrolled in more than one grupo only gets their first grupo
    (alphabetically) exported; the rest are listed in the console warning
    at the end so they can be checked/added by hand.
  - horario is rebuilt from the grupo's own schedule (Grupo.horarios), not
    from any personal partial-attendance window (Inscripcion.hora_inicio/
    hora_fin) -- those are rare (per DEVLOG) and not representable in this
    one-schedule-per-row sheet format anyway.

Usage:
    venv/Scripts/python.exe export_to_sheets.py [--sheet-id ID] [--dry-run]

Prompts for the platform superuser email/password interactively, same as
import_from_sheets.py.
"""
import argparse
import getpass
import os
import sys

import requests
from googleapiclient.discovery import build

sys.path.insert(0, os.path.dirname(__file__))
from modules.documentos.invoice_service import _credentials

DEFAULT_SPREADSHEET_ID = "1pXh-ad0QYrCFvCTB6s-hVB0AdxKFYC745YZFEY53qZ4"  # "Rangers Academy — Importación de alumnos"
TAB_TITLE = "Alumnos"
API_BASE = "https://academia-api-production-db7a.up.railway.app/api/v1/"

# Same order as create_import_template.py's COLUMNS, plus "marca" tacked on.
N_BASE_COLS = 22
DIA_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]


class ApiClient:
    def __init__(self, base_url, access_token):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {access_token}"

    def get(self, path):
        r = self.session.get(self.base_url + path)
        r.raise_for_status()
        return r.json()


def login(base_url, email, password):
    r = requests.post(base_url + "auth/login/", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access"]


def _fmt_fecha(iso):
    """YYYY-MM-DD -> DD/MM/YYYY, or ''."""
    if not iso:
        return ""
    try:
        y, m, d = iso.split("-")
        return f"{d}/{m}/{y}"
    except ValueError:
        return ""


def _fmt_horario(horarios):
    """[{"dia":0,"ini":"17:30","fin":"18:30"}, ...] -> 'Lun/Mié 17:30-18:30'
    (inverse of import_from_sheets.parse_horario). Blocks with the same
    ini/fin are grouped with '/', different ini/fin separated by ','."""
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


def build_row(alumno, pagadores_by_id, grupos_by_id, multi_grupo_warnings):
    grupos_detalle = alumno.get("grupos_detalle") or []
    grupo_detalle = grupos_detalle[0] if grupos_detalle else None
    if len(grupos_detalle) > 1:
        multi_grupo_warnings.append(
            f"{alumno['nombre']}: matriculado en {len(grupos_detalle)} grupos, "
            f"solo se exportó '{grupo_detalle['grupo_nombre']}' -- revisar el resto a mano."
        )
    grupo = grupos_by_id.get(grupo_detalle["grupo"]) if grupo_detalle else None

    pagador = pagadores_by_id.get(alumno.get("pagador")) or {}

    return [
        alumno.get("nombre") or "",        # nombre_alumno
        "",                                  # apellido_alumno (not stored separately -- see module docstring)
        _fmt_fecha(alumno.get("fecha_nacimiento")),
        alumno.get("dni") or "",
        alumno.get("telefono") or "",
        alumno.get("email") or "",
        alumno.get("nivel") or "",
        str(alumno["aviso_cumple_dias"]) if alumno.get("aviso_cumple_dias") is not None else "",
        alumno.get("notas") or "",
        pagador.get("nombre", ""),
        pagador.get("nif", ""),
        pagador.get("telefono", ""),
        pagador.get("email", ""),
        pagador.get("metodo", ""),
        pagador.get("frecuencia", ""),
        pagador.get("iban", ""),
        pagador.get("notas", ""),
        grupo.get("nombre", "") if grupo else "",
        grupo.get("nivel", "") if grupo else "",
        str(grupo["tarifa"]) if grupo else "",
        grupo.get("aula", "") if grupo else "",
        _fmt_horario(grupo_detalle["horarios"]) if grupo_detalle else "",
        alumno.get("marca") or "",           # extra column, see module docstring
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet-id", default=DEFAULT_SPREADSHEET_ID, help="Google Sheet spreadsheet ID")
    parser.add_argument("--api-base", default=API_BASE, help="Platform API base URL")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report without writing to the sheet")
    args = parser.parse_args()

    email = input("Platform email: ").strip()
    password = getpass.getpass("Platform password: ")
    try:
        access = login(args.api_base, email, password)
    except requests.HTTPError as e:
        print(f"Login failed: {e}")
        sys.exit(1)
    api = ApiClient(args.api_base, access)

    print("Descargando alumnos, pagadores y grupos de la plataforma...")
    alumnos = api.get("alumnos/")
    pagadores_by_id = {p["id"]: p for p in api.get("pagadores/")}
    grupos_by_id = {g["id"]: g for g in api.get("grupos/")}

    multi_grupo_warnings = []
    rows = [build_row(a, pagadores_by_id, grupos_by_id, multi_grupo_warnings) for a in alumnos]
    rows.sort(key=lambda r: r[0])  # nombre_alumno, so the sheet reads alphabetically

    print(f"{len(rows)} alumnos listos para exportar.")
    for w in multi_grupo_warnings:
        print(f"  ⚠ {w}")

    if args.dry_run:
        print("\n--dry-run: no se escribió nada en la Sheet.")
        return

    creds = _credentials()
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    # Clear whatever data rows are there now (rows 1-2 = headers, untouched)
    # before writing the fresh export, so a shorter new export never leaves
    # stale trailing rows from the previous (larger) one.
    sheets.spreadsheets().values().clear(
        spreadsheetId=args.sheet_id, range=f"{TAB_TITLE}!A3:W1000",
    ).execute()

    if rows:
        sheets.spreadsheets().values().update(
            spreadsheetId=args.sheet_id, range=f"{TAB_TITLE}!A3",
            valueInputOption="RAW", body={"values": rows},
        ).execute()

    print(f"\nEscrito en la Sheet: https://docs.google.com/spreadsheets/d/{args.sheet_id}/edit")


if __name__ == "__main__":
    main()
