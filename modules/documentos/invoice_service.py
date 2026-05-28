"""
Invoice/Receipt generation — ReportLab PDF + Google Drive storage.
Files land in: Drive → Facturas {year} → T{n} (…) → {num_doc}.pdf
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

# ── Constants ────────────────────────────────────────────────────────────────

GOLD  = colors.HexColor("#B08D57")
DARK  = colors.HexColor("#2D2D2D")
GRAY  = colors.HexColor("#6B6B6B")
LGRAY = colors.HexColor("#959595")
LGBG  = colors.HexColor("#F7F5F2")
WHITE = colors.white

IBAN = "ES10 2080 5020 0530 4003 9725"

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo",  6: "junio",   7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

METODOS_FACTURA = {"bizum", "transferencia", "tarjeta", "online"}

SCOPES = ["https://www.googleapis.com/auth/drive"]

# Credentials file sits at the Django project root (next to manage.py)
_HERE    = os.path.dirname(__file__)                        # modules/documentos/
_API_DIR = os.path.dirname(os.path.dirname(_HERE))         # project root
CREDS_PATH = os.path.join(_API_DIR, "google-credentials.json")


# ── Google Drive helpers ─────────────────────────────────────────────────────

def _drive():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


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
    if month <= 4:  return "T1 (Enero-Abril)"
    if month <= 8:  return "T2 (Mayo-Agosto)"
    return "T3 (Septiembre-Diciembre)"


def upload_to_drive(pdf_bytes: bytes, filename: str, year: int, month: int) -> str:
    """Upload PDF bytes to Drive. Returns the Drive file id."""
    service  = _drive()
    root_id  = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")          # may be None → service-account root
    year_id  = _folder(service, f"Facturas {year}", root_id)
    tri_id   = _folder(service, _trimester(month), year_id)

    meta  = {"name": filename, "parents": [tri_id]}
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


# ── Invoice numbering ────────────────────────────────────────────────────────

def _next_invoice_number(academia, prefix: str) -> str:
    """Determine next invoice number by querying the DB (no file-scan)."""
    from modules.documentos.models import Documento
    from modules.pagos.models import Pago

    year_short = str(date.today().year)[2:]
    suffix     = f"-{year_short}"
    max_num    = 236   # baseline: pre-existing paper invoices

    for qs in (
        Documento.objects.filter(academia=academia, num_doc__startswith=prefix, num_doc__endswith=suffix),
        Pago.objects.filter(academia=academia, num_doc__startswith=prefix, num_doc__endswith=suffix),
    ):
        for num_doc in qs.values_list("num_doc", flat=True):
            try:
                middle  = num_doc[len(prefix) : -len(suffix)]
                max_num = max(max_num, int(middle))
            except (ValueError, IndexError):
                pass

    return f"{prefix}{max_num + 1}{suffix}"


# ── Formatting helpers ───────────────────────────────────────────────────────

def _eur(amount) -> str:
    return "{:,.2f} €".format(float(amount)).replace(",", "X").replace(".", ",").replace("X", ".")


def _date_es(d) -> str:
    return f"{d.day} de {MESES_ES[d.month]} de {d.year}"


def _ps(name, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, **kw)


# ── PDF generation ───────────────────────────────────────────────────────────

def generate_pdf_bytes(
    academia_nombre, academia_dir, academia_ciudad, academia_tel, academia_cif,
    pagador_nombre, pagador_nif, pagador_tel, pagador_email,
    alumno_nombre, grupo_nombre,
    periodo, mensualidad, descuento, extras, total,
    metodo, concepto_libre, num_doc, fecha, tipo,
) -> bytes:

    if isinstance(fecha, str):
        fecha = date.fromisoformat(fecha)

    year_str, month_str = periodo.split("-")
    year, month  = int(year_str), int(month_str)
    mes_nombre   = MESES_ES[month].capitalize()
    title_label  = "FACTURA" if tipo == "factura" else "RECIBO"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )
    W      = A4[0] - 4*cm   # usable page width
    story  = []

    # ── Header ───────────────────────────────────────────────────────────────
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(logo_path):
        left_cell = Image(logo_path, width=4.5*cm, height=2*cm, kind="proportional")
    else:
        left_cell = Paragraph(
            "<font color='#B08D57' size=20><b>Cami&amp;Co</b></font>",
            _ps("logo", leading=24),
        )

    right_cell = Paragraph(
        f"<font color='#B08D57' size=26><b>{title_label}</b></font><br/>"
        f"<font color='#2D2D2D' size=11>N.º {num_doc}</font><br/>"
        f"<font color='#6B6B6B' size=9>Fecha: {_date_es(fecha)}</font>",
        _ps("rh", alignment=TA_RIGHT, leading=18),
    )

    hdr = Table([[left_cell, right_cell]], colWidths=[8*cm, W - 8*cm])
    hdr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",  (1, 0), (1,  0),  "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0, WHITE),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=8))

    # ── Quote ─────────────────────────────────────────────────────────────────
    story.append(Paragraph(
        "<i>\"It always seems impossible until it's done.\" — Nelson Mandela</i>",
        _ps("q", fontSize=8, textColor=LGRAY, alignment=TA_CENTER, spaceAfter=10, leading=12),
    ))

    # ── DE / PARA ─────────────────────────────────────────────────────────────
    st_lbl = _ps("lbl", fontSize=8,   textColor=GOLD, fontName="Helvetica-Bold", leading=12)
    st_val = _ps("val", fontSize=9.5, textColor=DARK, leading=14)
    st_dim = _ps("dim", fontSize=9,   textColor=GRAY, leading=13)

    def info_block(title_txt, lines):
        parts = [Paragraph(title_txt, st_lbl)]
        for line in lines:
            if line:
                parts.append(Paragraph(line, st_val))
        return parts

    emisor = info_block("DE:", [
        f"<b>{academia_nombre}</b>",
        academia_dir, academia_ciudad,
        f"Tel: {academia_tel}",
        f"CIF: {academia_cif}",
        f"IBAN: {IBAN}",
    ])
    pagador_lines = [f"<b>{pagador_nombre}</b>"]
    if pagador_nif:   pagador_lines.append(f"DNI/NIF: {pagador_nif}")
    if pagador_tel:   pagador_lines.append(f"Tel: {pagador_tel}")
    if pagador_email: pagador_lines.append(f"Email: {pagador_email}")
    para = info_block("PARA:", pagador_lines)

    info_tbl = Table([[emisor, para]], colWidths=[W / 2, W / 2])
    info_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0, WHITE),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 0.4*cm))

    # ── Alumno ────────────────────────────────────────────────────────────────
    story.append(Paragraph(
        "ALUMNO/S",
        _ps("al", fontSize=8, textColor=GOLD, fontName="Helvetica-Bold", spaceAfter=4),
    ))
    alumno_tbl = Table(
        [[Paragraph(f"<b>{alumno_nombre}</b>",
                    _ps("an", fontSize=11, textColor=DARK, alignment=TA_CENTER))]],
        colWidths=[W],
    )
    alumno_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LGBG),
        ("BOX",           (0, 0), (-1, -1), 1.5, GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(alumno_tbl)
    story.append(Spacer(1, 0.5*cm))

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
    for i, (desc, cant, precio, importe) in enumerate(items):
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

    n_items    = len(items)
    total_row  = 1 + n_items + 2

    style_cmds = [
        ("BACKGROUND",    (0, 0),        (-1, 0),        DARK),
        ("TOPPADDING",    (0, 0),        (-1, -1),       5),
        ("BOTTOMPADDING", (0, 0),        (-1, -1),       5),
        ("LEFTPADDING",   (0, 0),        (-1, -1),       4),
        ("RIGHTPADDING",  (0, 0),        (-1, -1),       4),
        ("GRID",          (0, 0),        (-1, -1),       0.5, colors.HexColor("#DDDDDD")),
        ("BACKGROUND",    (2, total_row), (3, total_row), GOLD),
    ]
    for i in range(n_items):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i + 1), (-1, i + 1), LGBG))
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
    story.append(HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=6))
    story.append(Paragraph(
        "TÉRMINOS DE PAGO",
        _ps("fp", fontSize=8, fontName="Helvetica-Bold", textColor=DARK,
            alignment=TA_CENTER, spaceAfter=4),
    ))
    story.append(Paragraph(
        "Los honorarios se gestionarán dentro de los <b>primeros 5 días naturales del mes</b>.",
        _ps("ft", fontSize=8, textColor=GRAY, alignment=TA_CENTER, spaceAfter=4, leading=12),
    ))
    story.append(Paragraph(IBAN, _ps("ib", fontSize=8, textColor=GRAY, alignment=TA_CENTER, spaceAfter=4)))
    story.append(Paragraph(
        "Operación exenta de IVA según el art. 20.Uno de la Ley 37/1992",
        _ps("ex", fontSize=8, textColor=LGRAY, alignment=TA_CENTER, fontName="Helvetica-Oblique"),
    ))

    doc.build(story)
    return buf.getvalue()


# ── Main entry point ─────────────────────────────────────────────────────────

def generate_invoice_for_pago(pago, tipo="factura"):
    """Generate PDF for a Pago, upload to Drive. Returns (num_doc, drive_file_id)."""
    acad    = pago.academia
    pagador = pago.pagador
    alumno  = pago.alumno
    grupo   = pago.grupo
    extras  = pago.extras or []
    metodo  = pago.metodo or ""

    es_fac   = metodo.lower() in METODOS_FACTURA if metodo else True
    tipo_doc = "factura" if es_fac else "recibo"
    prefix   = "CC" if es_fac else "REC"
    num_doc  = _next_invoice_number(acad, prefix)

    fecha = pago.fecha or date.today()
    if isinstance(fecha, str):
        fecha = date.fromisoformat(fecha)

    pdf_bytes = generate_pdf_bytes(
        academia_nombre = acad.academia_nombre or "Camila Pereiras Casal",
        academia_dir    = acad.academia_dir    or "C/ Pedro Soto Couselo 5, 2 B",
        academia_ciudad = "36995, Poio (Pontevedra)",
        academia_tel    = acad.academia_tel    or "698 183 419",
        academia_cif    = acad.academia_nif    or "39468659S",
        pagador_nombre  = pagador.nombre,
        pagador_nif     = getattr(pagador, "nif",      "") or "",
        pagador_tel     = getattr(pagador, "telefono", "") or "",
        pagador_email   = getattr(pagador, "email",    "") or "",
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
    )

    year_str, month_str = pago.periodo.split("-")
    drive_id = upload_to_drive(pdf_bytes, f"{num_doc}.pdf", int(year_str), int(month_str))

    return num_doc, drive_id
