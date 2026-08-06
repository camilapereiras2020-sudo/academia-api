"""
Invoice/Receipt generation — ReportLab PDF + Google Drive storage.
Files land in: Drive → <emisor folder> → Facturas {year} → T{n} → {num_doc}.pdf
"""
import io
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image,
)

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2 import service_account

# ── Colour palette ────────────────────────────────────────────────────────────

GOLD  = colors.HexColor("#B08D57")
DARK  = colors.HexColor("#2D2D2D")
GRAY  = colors.HexColor("#6B6B6B")
LGRAY = colors.HexColor("#959595")
LGBG  = colors.HexColor("#F7F5F2")
WHITE = colors.white

# ── Per-emisor PDF themes ─────────────────────────────────────────────────────

THEME_CAMIANDCO = {
    "accent":     GOLD,
    "accent_hex": "#B08D57",
    "bg":         LGBG,
    "logo_fn":    "Logo.png",
    "logo_w":     9 * cm,
    "logo_h":     5 * cm,
    "quote":      '"It always seems impossible until it\'s done." — Nelson Mandela',
}
THEME_RANGERS = {
    "accent":     colors.HexColor("#314922"),
    "accent_hex": "#314922",
    "bg":         colors.HexColor("#F5EDD6"),
    "logo_fn":    "rangers_logo.png",
    "logo_w":     3.5 * cm,
    "logo_h":     3.5 * cm,
    "quote":      '"The expert in anything was once a beginner." — Helen Hayes',
}

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo",  6: "junio",   7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

from modules.pagos.constants import tipo_doc_for_metodo

SCOPES = ["https://www.googleapis.com/auth/drive"]

_HERE      = os.path.dirname(__file__)
_API_DIR   = os.path.dirname(os.path.dirname(_HERE))
TOKEN_PATH = os.path.join(_API_DIR, ".google-token.json")


# ── Google Drive helpers ──────────────────────────────────────────────────────

def _credentials():
    """Return authenticated Google credentials (Drive/Sheets scope).

    Credential source priority:
      1. GOOGLE_TOKEN_JSON env var (Railway / production) — OAuth2 user token
         for cami.english2010@gmail.com, the actual owner of the Drive
         folders and the only credential with real storage quota on them
      2. .google-token.json file (local dev)
      3. GOOGLE_SERVICE_ACCOUNT_JSON env var — fallback only when no OAuth2
         token is configured at all. NOTE: service accounts have no storage
         quota on a personal Gmail Drive, so this can authenticate and read
         but cannot upload new files — it exists only so read-only checks
         (e.g. healthcheck.py) still run somewhere with no OAuth2 token set.
    """
    import json
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    raw = os.environ.get("GOOGLE_TOKEN_JSON", "")
    if raw:
        td = json.loads(raw)
    elif os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as f:
            td = json.load(f)
    else:
        sa_raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if sa_raw:
            return service_account.Credentials.from_service_account_info(
                json.loads(sa_raw), scopes=SCOPES
            )
        raise RuntimeError(
            "No Google Drive credentials found. "
            "Set GOOGLE_TOKEN_JSON env var or run setup_drive_auth.py locally."
        )

    creds = Credentials(
        token         = td.get("token"),
        refresh_token = td.get("refresh_token"),
        token_uri     = td.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id     = td.get("client_id"),
        client_secret = td.get("client_secret"),
        scopes        = td.get("scopes"),
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        if os.path.exists(TOKEN_PATH):
            td.update({"token": creds.token})
            with open(TOKEN_PATH, "w") as f:
                json.dump(td, f)

    return creds


def _drive():
    """Return an authenticated Drive service (service account or OAuth2 user credentials)."""
    return build("drive", "v3", credentials=_credentials(), cache_discovery=False)


def _folder(service, name, parent_id=None):
    """Return the id of a Drive folder, creating it if it doesn't exist."""
    q = f"mimeType='application/vnd.google-apps.folder' and name='{name}' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    results = service.files().list(q=q, fields="files(id)").execute()
    hits = results.get("files", [])
    if hits:
        return hits[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    return service.files().create(body=meta, fields="id").execute()["id"]


def _trimester(month):
    if month <= 3:  return "T1 (Enero-Marzo)"
    if month <= 6:  return "T2 (Abril-Junio)"
    if month <= 9:  return "T3 (Julio-Septiembre)"
    return "T4 (Octubre-Diciembre)"


def upload_to_drive(pdf_bytes: bytes, filename: str, year: int, month: int,
                    folder_id: str = None, subfolder: str = None) -> str:
    """Upload PDF bytes to Drive. Returns the Drive file id.

    folder_id: root Drive folder for this emisor. Falls back to
    GOOGLE_DRIVE_FOLDER_ID env var if not provided.
    subfolder: if given (e.g. "Anuladas"), replaces the T1-T4 quarter
    folder — used to segregate voided documents from the live ones.
    """
    root_id = folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if not root_id:
        raise ValueError(
            "No Drive folder configured. Set drive_folder_id on the Emisor "
            "or set GOOGLE_DRIVE_FOLDER_ID env var."
        )
    service  = _drive()
    year_id  = _folder(service, f"Facturas {year}", root_id)
    leaf_id  = _folder(service, subfolder or _trimester(month), year_id)

    meta  = {"name": filename, "parents": [leaf_id]}
    media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf", resumable=False)
    file  = service.files().create(body=meta, media_body=media, fields="id").execute()
    return file["id"]


def download_from_drive(file_id: str) -> bytes:
    """Download file content from Drive. Returns raw bytes."""
    service    = _drive()
    request    = service.files().get_media(fileId=file_id)
    buf        = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done       = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def delete_drive_file(file_id: str) -> None:
    _drive().files().delete(fileId=file_id).execute()


# ── Invoice numbering ─────────────────────────────────────────────────────────

def _next_invoice_number(emisor, tipo: str) -> str:
    """Atomically allocate the next doc number for this emisor+tipo.

    Numbering redesign: replaces the old DB-scan-for-max approach with a
    counter field on Emisor (factura_counter/recibo_counter), incremented
    and saved in place. "efectivo" (cash) no longer has its own isolated
    sequence — tipo_doc_for_metodo folds it into "recibo", so this function
    only ever sees "factura" or "recibo" now (recibo_efectivo_* fields on
    Emisor are legacy/historical-only, kept for old documents' readability).

    Both buckets use prefix + counter + year suffix (e.g. "CC237-26"). The
    counter resets to each Emisor's baseline every calendar year — same
    externally-visible behaviour as the old suffix-filtered scan, just
    without re-scanning the DB on every call.

    IMPORTANT: caller must pass an `emisor` fetched with select_for_update()
    inside the same transaction, and hold that lock until this call
    (which both reads and writes the counter) returns — otherwise two
    concurrent requests can read the same counter value and allocate the
    same number.
    """
    year   = date.today().year
    suffix = f"-{str(year)[2:]}"

    if tipo == "factura":
        prefix, baseline          = emisor.factura_prefix, emisor.factura_baseline
        counter, counter_year     = emisor.factura_counter, emisor.factura_counter_year
        counter_field, year_field = "factura_counter", "factura_counter_year"
    else:
        # "recibo" — includes former "recibo_efectivo"/cash pagos, now
        # folded into this same bucket (see tipo_doc_for_metodo).
        prefix, baseline          = emisor.recibo_prefix, emisor.recibo_baseline
        counter, counter_year     = emisor.recibo_counter, emisor.recibo_counter_year
        counter_field, year_field = "recibo_counter", "recibo_counter_year"

    if counter_year != year:
        counter = baseline

    next_num = counter + 1
    setattr(emisor, counter_field, next_num)
    setattr(emisor, year_field, year)
    emisor.save(update_fields=[counter_field, year_field])

    return f"{prefix}{next_num}{suffix}"


# ── Formatting helpers ────────────────────────────────────────────────────────

def _eur(amount) -> str:
    return "{:,.2f} €".format(float(amount)).replace(",", "X").replace(".", ",").replace("X", ".")


def _date_es(d) -> str:
    return f"{d.day} de {MESES_ES[d.month]} de {d.year}"


def _ps(name, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, **kw)


# ── PDF generation ────────────────────────────────────────────────────────────

def _draw_watermark(canvas, doc_, text):
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 90)
    canvas.setFillColor(colors.red)
    canvas.setFillAlpha(0.18)
    canvas.translate(A4[0] / 2, A4[1] / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, text)
    canvas.restoreState()


def generate_pdf_bytes(
    academia_nombre, academia_autonoma, academia_dir, academia_ciudad,
    academia_tel, academia_email, academia_cif, iban,
    pagador_nombre, pagador_nif, pagador_tel, pagador_email,
    alumno_nombre, grupo_nombre,
    periodo, mensualidad, descuento, extras, total,
    metodo, concepto_libre, num_doc, fecha, tipo,
    theme: dict = None,
    watermark: str = None,
) -> bytes:

    t          = theme or THEME_CAMIANDCO
    accent     = t["accent"]
    accent_hex = t["accent_hex"]
    bg         = t["bg"]
    logo_fn    = t["logo_fn"]
    logo_w     = t["logo_w"]
    logo_h     = t["logo_h"]
    quote      = t["quote"]

    if isinstance(fecha, str):
        fecha = date.fromisoformat(fecha)

    year_str, month_str = periodo.split("-")
    year, month  = int(year_str), int(month_str)
    mes_nombre   = MESES_ES[month].capitalize()
    title_label  = "FACTURA" if tipo == "factura" else "RECIBO"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2.2*cm, rightMargin=2.2*cm,
        topMargin=2.5*cm, bottomMargin=2.5*cm,
    )
    W     = A4[0] - 4.4*cm
    story = []

    # ── Header ───────────────────────────────────────────────────────────────
    logo_path = os.path.join(os.path.dirname(__file__), logo_fn)
    if not os.path.exists(logo_path):
        logo_path = os.path.join(os.path.dirname(__file__), logo_fn.lower())
    if os.path.exists(logo_path):
        left_cell = Image(logo_path, width=logo_w, height=logo_h, kind="proportional")
    else:
        left_cell = Paragraph(
            f"<font color='{accent_hex}' size=22><b>{academia_nombre}</b></font>",
            _ps("logo", leading=26),
        )

    right_cell = Paragraph(
        f"<font color='{accent_hex}' size=28><b>{title_label}</b></font><br/>"
        f"<font color='#2D2D2D' size=12><b>N.º {num_doc}</b></font><br/>"
        f"<font color='#2D2D2D' size=11>Fecha: {_date_es(fecha)}</font>",
        _ps("rh", alignment=TA_RIGHT, leading=22),
    )

    hdr = Table([[left_cell, right_cell]], colWidths=[logo_w, W - logo_w])
    hdr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",  (1, 0), (1,  0),  "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0, WHITE),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=accent, spaceAfter=10))

    # ── Quote ─────────────────────────────────────────────────────────────────
    story.append(Paragraph(
        f"<i>{quote}</i>",
        _ps("q", fontSize=8.5, textColor=LGRAY, alignment=TA_CENTER, spaceAfter=14, leading=13),
    ))

    # ── DE / PARA ─────────────────────────────────────────────────────────────
    st_lbl = _ps("lbl", fontSize=8,   textColor=accent, fontName="Helvetica-Bold", leading=12)
    st_val = _ps("val", fontSize=9.5, textColor=DARK,   leading=14)
    st_dim = _ps("dim", fontSize=9,   textColor=GRAY,   leading=13)

    def info_block(title_txt, lines):
        parts = [Paragraph(title_txt, st_lbl)]
        for line in lines:
            if line:
                parts.append(Paragraph(line, st_val))
        return parts

    emisor_lines = [
        f"<b>{academia_nombre}</b>",
        academia_autonoma,
        f"NIF: {academia_cif}",
        f"{academia_dir}, {academia_ciudad}",
        f"Tel: {academia_tel}",
        academia_email,
    ]
    if iban:
        emisor_lines.append(f"IBAN: {iban}")
    emisor_block = info_block("DE:", emisor_lines)

    pagador_lines = [f"<b>{pagador_nombre}</b>"]
    if pagador_nif:   pagador_lines.append(f"DNI/NIF: {pagador_nif}")
    if pagador_tel:   pagador_lines.append(f"Tel: {pagador_tel}")
    if pagador_email: pagador_lines.append(f"Email: {pagador_email}")
    para_block = info_block("PARA:", pagador_lines)

    info_tbl = Table([[emisor_block, para_block]], colWidths=[W / 2, W / 2])
    info_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0, WHITE),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 0.6*cm))

    # ── Alumno + Horario ──────────────────────────────────────────────────────
    story.append(Paragraph(
        "ALUMNO/S",
        _ps("al", fontSize=8, textColor=accent, fontName="Helvetica-Bold", spaceAfter=4),
    ))
    alumno_tbl = Table(
        [[Paragraph(f"<b>{alumno_nombre}</b>",
                    _ps("an", fontSize=12, textColor=DARK, alignment=TA_CENTER))]],
        colWidths=[W],
    )
    alumno_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("BOX",           (0, 0), (-1, -1), 1.5, accent),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(alumno_tbl)

    if grupo_nombre:
        story.append(Spacer(1, 0.25*cm))
        story.append(Paragraph(
            "GRUPO / HORARIO",
            _ps("gl", fontSize=8, textColor=accent, fontName="Helvetica-Bold", spaceAfter=3),
        ))
        grupo_tbl = Table(
            [[Paragraph(grupo_nombre, _ps("gn", fontSize=10, textColor=DARK, alignment=TA_CENTER))]],
            colWidths=[W],
        )
        grupo_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), bg),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(grupo_tbl)

    story.append(Spacer(1, 0.6*cm))

    # ── Items table ───────────────────────────────────────────────────────────
    if concepto_libre:
        desc_main = concepto_libre
    else:
        desc_main = f"Clases de inglés — {mes_nombre} {year}"
        if grupo_nombre:
            desc_main += f" ({grupo_nombre})"

    items = [(desc_main, "1", _eur(mensualidad), _eur(mensualidad))]
    if float(descuento) > 0:
        items.append(("Descuento", "1", f"−{_eur(descuento)}", f"−{_eur(descuento)}"))
    for ex in (extras or []):
        imp = float(ex.get("importe", 0))
        items.append((ex.get("concepto", "Extra"), "1", _eur(imp), _eur(imp)))

    extras_total = sum(float(ex.get("importe", 0)) for ex in (extras or []))
    subtotal     = float(mensualidad) - float(descuento)

    col_w = [W * 0.52, W * 0.12, W * 0.18, W * 0.18]

    st_hdr = _ps("h",  fontSize=9,  textColor=WHITE, fontName="Helvetica-Bold")
    st_hc  = _ps("hc", fontSize=9,  textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_CENTER)
    st_hr  = _ps("hr", fontSize=9,  textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_RIGHT)
    st_cel = _ps("ce", fontSize=10, textColor=DARK)
    st_cc  = _ps("cc", fontSize=10, textColor=DARK, alignment=TA_CENTER)
    st_cr  = _ps("cr", fontSize=10, textColor=DARK, alignment=TA_RIGHT)

    table_data = [[
        Paragraph("Descripción", st_hdr),
        Paragraph("Cant.", st_hc),
        Paragraph("Precio", st_hr),
        Paragraph("Importe", st_hr),
    ]]
    for desc, cant, precio, importe in items:
        table_data.append([
            Paragraph(desc, st_cel),
            Paragraph(cant, st_cc),
            Paragraph(precio, st_cr),
            Paragraph(importe, st_cr),
        ])

    for label, amount, is_total in [
        ("SUBTOTAL", _eur(subtotal),     False),
        ("OTROS",    _eur(extras_total), False),
        ("TOTAL",    _eur(total),        True),
    ]:
        fc   = WHITE if is_total else DARK
        size = 11 if is_total else 10
        st_s = _ps(f"s{label}", fontSize=size, textColor=fc,
                   fontName="Helvetica-Bold", alignment=TA_RIGHT)
        table_data.append(["", "", Paragraph(label, st_s), Paragraph(amount, st_s)])

    n_items   = len(items)
    total_row = 1 + n_items + 2

    style_cmds = [
        ("BACKGROUND",    (0, 0),          (-1, 0),          DARK),
        ("TOPPADDING",    (0, 0),          (-1, -1),         5),
        ("BOTTOMPADDING", (0, 0),          (-1, -1),         5),
        ("LEFTPADDING",   (0, 0),          (-1, -1),         4),
        ("RIGHTPADDING",  (0, 0),          (-1, -1),         4),
        ("GRID",          (0, 0),          (-1, -1),         0.5, colors.HexColor("#DDDDDD")),
        ("BACKGROUND",    (2, total_row),  (3, total_row),   accent),
    ]
    for i in range(n_items):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i + 1), (-1, i + 1), bg))
    for si in range(3):
        ri = 1 + n_items + si
        style_cmds.append(("SPAN", (0, ri), (1, ri)))

    items_tbl = Table(table_data, colWidths=col_w)
    items_tbl.setStyle(TableStyle(style_cmds))
    story.append(items_tbl)

    if metodo:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(
            f"<font color='#6B6B6B'>Método de pago: </font><b>{metodo.capitalize()}</b>",
            _ps("mp", fontSize=9, textColor=DARK, leading=14),
        ))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=accent, spaceAfter=6))
    story.append(Paragraph(
        "TÉRMINOS DE PAGO",
        _ps("fp", fontSize=8, fontName="Helvetica-Bold", textColor=DARK,
            alignment=TA_CENTER, spaceAfter=4),
    ))
    story.append(Paragraph(
        "Los honorarios se gestionarán dentro de los <b>primeros 5 días naturales del mes</b>.",
        _ps("ft", fontSize=8, textColor=GRAY, alignment=TA_CENTER, spaceAfter=4, leading=12),
    ))
    if iban:
        story.append(Paragraph(iban, _ps("ib", fontSize=8, textColor=GRAY, alignment=TA_CENTER, spaceAfter=4)))
    story.append(Paragraph(
        "Operación exenta de IVA según el art. 20.Uno de la Ley 37/1992",
        _ps("ex", fontSize=8, textColor=LGRAY, alignment=TA_CENTER, fontName="Helvetica-Oblique"),
    ))

    if watermark:
        stamp = lambda c, d: _draw_watermark(c, d, watermark)
        doc.build(story, onFirstPage=stamp, onLaterPages=stamp)
    else:
        doc.build(story)
    return buf.getvalue()


# ── Main entry point ──────────────────────────────────────────────────────────

def _pagador_display_fields(pagador, alumno):
    """Returns (nombre, nif, telefono, email) to render on the invoice/recibo.
    If there's no Pagador on file but the alumno is an adult who pays for
    themself (Alumno.es_adulto), fall back to the alumno's own contact data
    instead of leaving the document blank."""
    if pagador is not None:
        return (
            pagador.nombre,
            getattr(pagador, "nif", "") or "",
            getattr(pagador, "telefono", "") or "",
            getattr(pagador, "email", "") or "",
        )
    if alumno is not None and getattr(alumno, "es_adulto", False):
        return (
            alumno.nombre,
            getattr(alumno, "dni", "") or "",
            getattr(alumno, "telefono", "") or "",
            getattr(alumno, "email", "") or "",
        )
    return ("", "", "", "")


def generate_invoice_for_pago(pago, tipo="factura"):
    """Generate PDF for a Pago using its Emisor, upload to Drive.
    Returns (num_doc, drive_file_id, tipo_doc). tipo_doc is the authoritative
    bucket ("factura"/"recibo" — "efectivo"/cash folds into "recibo" as of
    the numbering redesign) derived from pago.metodo — callers should store
    *this* on the Documento, not their own guess (the `tipo` param above is
    legacy and not used for numbering).
    """
    alumno_adulto_sin_pagador = (
        not pago.pagador_id and pago.alumno_id and getattr(pago.alumno, "es_adulto", False)
    )
    if pago.estado_carga == "pendiente_completar" or not pago.alumno_id or (
        not pago.pagador_id and not alumno_adulto_sin_pagador
    ):
        raise ValueError(
            f"Pago {pago.id} está incompleto (estado_carga={pago.estado_carga!r}, "
            f"alumno={pago.alumno_id}, pagador={pago.pagador_id}) — "
            "complétalo antes de generar factura/recibo."
        )

    emisor  = pago.emisor
    if emisor is None:
        raise ValueError(f"Pago {pago.id} has no emisor assigned.")

    pagador = pago.pagador
    alumno  = pago.alumno
    grupo   = pago.grupo
    extras  = pago.extras or []
    metodo  = pago.metodo or ""
    pagador_nombre, pagador_nif, pagador_tel, pagador_email = _pagador_display_fields(pagador, alumno)

    tipo_doc = tipo_doc_for_metodo(metodo)
    # A bulk-imported draft may already carry a pre-assigned number (e.g. from
    # an external Bizum/TaxFix reconciliation) — honor it instead of
    # allocating a new one.
    num_doc = pago.numero_factura_reservado
    if not num_doc:
        # Two concurrent requests for the same emisor+tipo must not allocate
        # the same "next number". Locking the Emisor row (Postgres in prod;
        # a harmless no-op on SQLite, which doesn't support row locks — fine
        # for single-user local dev), then reading+incrementing its counter
        # while the lock is held, closes the race: a second request blocks
        # on the lock, and once it gets it, re-fetches the row and sees the
        # already-incremented counter. Must use the freshly locked instance
        # (not the `emisor` fetched before the lock) — _next_invoice_number
        # reads counter fields off the Python object now instead of
        # re-scanning the DB, so a stale object would hand out a stale
        # number.
        from django.db import transaction
        from modules.documentos.models import Emisor as EmisorModel
        with transaction.atomic():
            locked_emisor = EmisorModel.objects.select_for_update().get(pk=emisor.pk)
            num_doc = _next_invoice_number(locked_emisor, tipo_doc)
            pago.numero_factura_reservado = num_doc
            pago.save(update_fields=["numero_factura_reservado"])

    fecha = pago.fecha or date.today()
    if isinstance(fecha, str):
        fecha = date.fromisoformat(fecha)

    theme = THEME_RANGERS if getattr(emisor, "slug", "") == "rangers" else THEME_CAMIANDCO

    pdf_bytes = generate_pdf_bytes(
        academia_nombre   = emisor.nombre,
        academia_autonoma = emisor.autonoma,
        academia_dir      = emisor.direccion,
        academia_ciudad   = emisor.ciudad,
        academia_tel      = emisor.telefono,
        academia_email    = getattr(emisor, "email", "") or "",
        academia_cif      = emisor.nif,
        iban              = emisor.iban,
        pagador_nombre  = pagador_nombre,
        pagador_nif     = pagador_nif,
        pagador_tel     = pagador_tel,
        pagador_email   = pagador_email,
        alumno_nombre   = alumno.nombre,
        grupo_nombre    = grupo.nombre if grupo else "",
        periodo         = pago.periodo,
        mensualidad     = pago.mensualidad,
        descuento       = pago.descuento,
        extras          = extras,
        total           = pago.total,
        metodo          = metodo,
        concepto_libre  = getattr(pago, "concepto_libre", "") or "",
        num_doc         = num_doc,
        fecha           = fecha,
        tipo            = tipo_doc,
        theme           = theme,
    )

    # Drive quarter-folder placement follows the actual invoice date, not the
    # billed periodo (a July-dated invoice for June's service goes in T3).
    folder_id = emisor.drive_folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID") or ""
    drive_id  = upload_to_drive(pdf_bytes, f"{num_doc}.pdf", fecha.year, fecha.month, folder_id)

    return num_doc, drive_id, tipo_doc


def _rerender_documento_pdf(documento, watermark: str = None, subfolder: str = None) -> str:
    """Shared by regenerate_anulada_pdf/reactivar_documento: re-render a
    Documento's PDF (reusing its existing num_doc — never consumes a new
    invoice number) and move it in Drive, deleting the old file. Returns the
    new Drive file id.
    """
    pago = documento.pago
    if pago is None:
        raise ValueError(f"Documento {documento.id} has no linked Pago; cannot regenerate.")
    emisor = pago.emisor
    if emisor is None:
        raise ValueError(f"Pago {pago.id} has no emisor assigned.")

    pagador, alumno, grupo = pago.pagador, pago.alumno, pago.grupo
    extras = pago.extras or []
    metodo = pago.metodo or ""
    fecha  = pago.fecha or date.today()
    if isinstance(fecha, str):
        fecha = date.fromisoformat(fecha)
    theme = THEME_RANGERS if getattr(emisor, "slug", "") == "rangers" else THEME_CAMIANDCO
    pagador_nombre, pagador_nif, pagador_tel, pagador_email = _pagador_display_fields(pagador, alumno)

    pdf_bytes = generate_pdf_bytes(
        academia_nombre   = emisor.nombre,
        academia_autonoma = emisor.autonoma,
        academia_dir      = emisor.direccion,
        academia_ciudad   = emisor.ciudad,
        academia_tel      = emisor.telefono,
        academia_email    = getattr(emisor, "email", "") or "",
        academia_cif      = emisor.nif,
        iban              = emisor.iban,
        pagador_nombre  = pagador_nombre,
        pagador_nif     = pagador_nif,
        pagador_tel     = pagador_tel,
        pagador_email   = pagador_email,
        alumno_nombre   = alumno.nombre if alumno else "",
        grupo_nombre    = grupo.nombre if grupo else "",
        periodo         = pago.periodo,
        mensualidad     = pago.mensualidad,
        descuento       = pago.descuento,
        extras          = extras,
        total           = pago.total,
        metodo          = metodo,
        concepto_libre  = getattr(pago, "concepto_libre", "") or "",
        num_doc         = documento.num_doc,
        fecha           = fecha,
        tipo            = documento.tipo,
        theme           = theme,
        watermark       = watermark,
    )

    folder_id = emisor.drive_folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID") or ""
    new_id = upload_to_drive(
        pdf_bytes, f"{documento.num_doc}.pdf",
        fecha.year, fecha.month, folder_id, subfolder=subfolder,
    )

    if documento.s3_key:
        try:
            delete_drive_file(documento.s3_key)
        except Exception as e:
            print(f"[rerender] could not remove old Drive file {documento.s3_key}: {e}")

    return new_id


def regenerate_anulada_pdf(documento) -> str:
    """Re-render a Documento's PDF with an ANULADA watermark and move it to the
    Anuladas subfolder in Drive. Reuses the existing num_doc — does not
    consume a new invoice number. Returns the new Drive file id.
    """
    return _rerender_documento_pdf(documento, watermark="ANULADA", subfolder="Anuladas")


def reactivar_documento(documento) -> str:
    """Reverse of regenerate_anulada_pdf: re-render the PDF without the
    ANULADA watermark and move it back to the normal (non-Anuladas) Drive
    folder. For correcting a wrongly-voided document — the caller is
    responsible for resetting estado/anulada_at/motivo_anulacion afterward.
    """
    return _rerender_documento_pdf(documento, watermark=None, subfolder=None)
