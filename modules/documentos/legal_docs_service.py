"""
Legal document generation — pre-filled, print-and-sign PDFs (ReportLab).

Scope (Nivel 1 of the RGPD/cancelación document rollout): these PDFs come
out with the student's real data already in place — name, date of birth,
group, payer/tutor name, and the correct Emisor (Cami&Co / Rangers Academy)
legal identity — so staff only has to print, hand the sheet to the family,
and file the signed paper. No signature capture yet (that's a possible
"Nivel 2" building on this).

Visually matches invoice_service.py's Rangers/Cami&Co themes so these
documents feel like part of the same platform as the invoices — same
accent colours, same logo, same footer style.

Text content is the RGPD/LOPD legal package drafted 2026-08-30 (image
consent, cancellation policy) — see claude/gdpr-lopd-documentos-2026-08.md
in the project. Kept in sync manually: if the legal wording of either
document changes, update the PARRAFOS_* constants below to match.
"""
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image,
)

from .invoice_service import THEME_RANGERS, THEME_CAMIANDCO, _date_es, MESES_ES

MARCA_TO_THEME = {
    "rangers_academy": THEME_RANGERS,
    "cami_and_co": THEME_CAMIANDCO,
}
MARCA_TO_EMISOR_SLUG = {
    "cami_and_co": "camiandco",
    "rangers_academy": "rangers",
}

DARK = colors.HexColor("#2D2D2D")
GRAY = colors.HexColor("#6B6B6B")


def _ps(name, **kw):
    return ParagraphStyle(name, **kw)


def _emisor_for_alumno(alumno):
    """Same lookup pagos.views._emisor_for_marca uses — the real legal
    identity (nombre/NIF/dirección) for whichever brand this alumno
    belongs to, so the document doesn't need bracketed placeholders for
    the responsable del tratamiento."""
    from modules.documentos.models import Emisor
    slug = MARCA_TO_EMISOR_SLUG.get(alumno.marca, "camiandco")
    return Emisor.objects.filter(academia=alumno.academia, slug=slug).first()


def _grupo_actual(alumno):
    insc = alumno.inscripciones.select_related("grupo").first()
    return insc.grupo.nombre if insc else ""


def _pagador_nombre(alumno):
    if alumno.pagador_id:
        return alumno.pagador.nombre
    if alumno.es_adulto:
        return alumno.nombre
    return ""


def _base_doc(buf):
    return SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2.2 * cm, bottomMargin=2.2 * cm,
    )


def _header(story, emisor, theme, title_label):
    accent, accent_hex, logo_fn, logo_w, logo_h = (
        theme["accent"], theme["accent_hex"], theme["logo_fn"], theme["logo_w"], theme["logo_h"],
    )
    import os
    logo_path = os.path.join(os.path.dirname(__file__), logo_fn)
    if os.path.exists(logo_path):
        left_cell = Image(logo_path, width=logo_w * 0.7, height=logo_h * 0.7, kind="proportional")
    else:
        left_cell = Paragraph(
            f"<font color='{accent_hex}' size=18><b>{emisor.nombre if emisor else ''}</b></font>",
            _ps("logo", leading=22),
        )
    right_cell = Paragraph(
        f"<font color='{accent_hex}' size=18><b>{title_label}</b></font>",
        _ps("rh", alignment=TA_RIGHT, leading=22),
    )
    W = A4[0] - 4.4 * cm
    hdr = Table([[left_cell, right_cell]], colWidths=[logo_w * 0.7, W - logo_w * 0.7])
    hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(hdr)
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=accent, spaceAfter=10))


def _responsable_block(emisor):
    if not emisor:
        return "Responsable del tratamiento: (Emisor no configurado para esta marca)"
    return (
        f"<b>{emisor.nombre}</b> ({emisor.autonoma}) — NIF {emisor.nif} — "
        f"{emisor.direccion}, {emisor.ciudad}"
        + (f" — {emisor.email}" if emisor.email else "")
    )


def _datos_alumno_tabla(alumno, W, accent, bg):
    fnac = _date_es(alumno.fecha_nacimiento) if alumno.fecha_nacimiento else "____________"
    grupo = _grupo_actual(alumno) or "____________"
    data = [[
        Paragraph(f"<b>Alumno/a:</b> {alumno.nombre}", _ps("d1", fontSize=10, textColor=DARK)),
        Paragraph(f"<b>Fecha de nacimiento:</b> {fnac}", _ps("d2", fontSize=10, textColor=DARK)),
    ], [
        Paragraph(f"<b>Grupo/curso:</b> {grupo}", _ps("d3", fontSize=10, textColor=DARK)),
        Paragraph(f"<b>Fecha del documento:</b> {_date_es(date.today())}", _ps("d4", fontSize=10, textColor=DARK)),
    ]]
    tbl = Table(data, colWidths=[W / 2, W / 2])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 1, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return tbl


def _firma_tabla(W, pagador_nombre):
    st = _ps("f", fontSize=9, textColor=DARK, leading=14)
    c1 = Paragraph(
        f"<b>Padre / Madre / Tutor/a 1</b><br/><br/>Nombre: {pagador_nombre}"
        "<br/><br/>DNI/NIE: ______________<br/><br/>Firma:<br/><br/><br/>Fecha: ______________",
        st,
    )
    c2 = Paragraph(
        "<b>Padre / Madre / Tutor/a 2 (si procede)</b><br/><br/>Nombre: ______________________"
        "<br/><br/>DNI/NIE: ______________<br/><br/>Firma:<br/><br/><br/>Fecha: ______________",
        st,
    )
    tbl = Table([[c1, c2]], colWidths=[W / 2, W / 2])
    tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#DDDDDD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#DDDDDD")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


# ── Documento 1: Consentimiento de imagen ───────────────────────────────────

def render_consentimiento_imagen_pdf(alumno) -> bytes:
    theme = MARCA_TO_THEME.get(alumno.marca, THEME_CAMIANDCO)
    emisor = _emisor_for_alumno(alumno)
    buf = io.BytesIO()
    doc = _base_doc(buf)
    W = A4[0] - 4.4 * cm
    story = []
    _header(story, emisor, theme, "CONSENTIMIENTO DE IMAGEN")

    body = _ps("body", fontSize=9.5, textColor=DARK, leading=14, alignment=TA_JUSTIFY, spaceAfter=8)
    lbl = _ps("lbl", fontSize=9.5, textColor=theme["accent"], fontName="Helvetica-Bold", spaceAfter=4, spaceBefore=10)

    story.append(Paragraph(_responsable_block(emisor), body))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_datos_alumno_tabla(alumno, W, theme["accent"], theme["bg"]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph(
        "Este documento es independiente y voluntario. No firmarlo, firmarlo solo parcialmente, "
        "o revocarlo más adelante, no supone ninguna consecuencia para la matriculación, "
        "permanencia o trato del alumno/a en la Academia.",
        body,
    ))
    story.append(Paragraph("Finalidades (marque únicamente las que autoriza):", lbl))
    for texto in [
        "Uso en la página web oficial de la Academia.",
        "Uso en perfiles de redes sociales de la Academia (Instagram, Facebook y similares).",
        "Uso en folletos, carteles y material publicitario impreso o digital.",
        "Uso interno exclusivamente pedagógico (visible solo por el profesorado y el propio alumno/a).",
    ]:
        story.append(Paragraph(f"[&nbsp;&nbsp;&nbsp;]&nbsp;&nbsp;{texto}", body))

    story.append(Paragraph(
        "El consentimiento es revocable en cualquier momento, sin necesidad de justificar el motivo, "
        "dirigiéndose a la Academia en los datos de contacto indicados arriba. Derechos de acceso, "
        "rectificación, supresión, oposición, limitación y portabilidad ante la misma dirección; "
        "reclamación ante la Agencia Española de Protección de Datos (www.aepd.es).",
        body,
    ))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "Declaro haber leído y comprendido este documento, y otorgo mi consentimiento únicamente "
        "para las finalidades marcadas arriba, de forma libre y sin que condicione la matriculación.",
        body,
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_firma_tabla(W, _pagador_nombre(alumno)))

    doc.build(story)
    return buf.getvalue()


# ── Documento 2: Política de cancelación (acuse de recibo firmado) ─────────

def _parrafos_cancelacion(marca: str):
    if marca == "rangers_academy":
        return [
            ("Rangers Academy — grupos con horario fijo", [
                "La ausencia puntual de un alumno a una clase no genera reembolso ni recuperación individual.",
                "La baja de matrícula se comunica con 15 días de antelación al mes siguiente; el mes en curso se abona íntegro y no hay penalización adicional.",
                "Ausencias de 2+ semanas por enfermedad justificada: matrícula congelable o recuperación en otro grupo del mismo nivel, sin coste.",
                "Si la Academia cancela una clase, se avisa en 24h y se recupera en un plazo máximo de 2 semanas, o se descuenta proporcionalmente.",
            ]),
        ]
    return [
        ("Cami&Co — clases individuales o en grupo reducido", [
            "Contratación online: derecho de desistimiento de 14 días naturales sin necesidad de justificar el motivo.",
            "Cancelar una clase con 24h o más de antelación: se reprograma sin coste. Con menos de 24h o no presentarse: se considera clase impartida.",
            "Si la profesora cancela la clase: reprogramación en 7 días o descuento equivalente en la siguiente factura.",
            "Baja de un bono: reembolso proporcional a las clases no disfrutadas, con gastos de gestión no superiores al 10%.",
        ]),
    ]


def render_politica_cancelacion_pdf(alumno) -> bytes:
    theme = MARCA_TO_THEME.get(alumno.marca, THEME_CAMIANDCO)
    emisor = _emisor_for_alumno(alumno)
    buf = io.BytesIO()
    doc = _base_doc(buf)
    W = A4[0] - 4.4 * cm
    story = []
    _header(story, emisor, theme, "POLÍTICA DE CANCELACIÓN — ACUSE DE RECIBO")

    body = _ps("body", fontSize=9.5, textColor=DARK, leading=14, alignment=TA_JUSTIFY, spaceAfter=8)
    lbl = _ps("lbl", fontSize=10, textColor=theme["accent"], fontName="Helvetica-Bold", spaceAfter=4, spaceBefore=10)

    story.append(Paragraph(_responsable_block(emisor), body))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_datos_alumno_tabla(alumno, W, theme["accent"], theme["bg"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "Al firmar, la familia confirma haber recibido y comprendido las condiciones de cancelación "
        "aplicables a su matrícula, resumidas a continuación (documento completo disponible en la Academia):",
        body,
    ))

    for titulo, puntos in _parrafos_cancelacion(alumno.marca):
        story.append(Paragraph(titulo, lbl))
        for p in puntos:
            story.append(Paragraph(f"•&nbsp;&nbsp;{p}", body))

    story.append(Spacer(1, 0.4 * cm))
    story.append(_firma_tabla(W, _pagador_nombre(alumno)))

    doc.build(story)
    return buf.getvalue()


RENDERERS = {
    "autorizacion_imagen": render_consentimiento_imagen_pdf,
    "politica_cancelacion": render_politica_cancelacion_pdf,
}
