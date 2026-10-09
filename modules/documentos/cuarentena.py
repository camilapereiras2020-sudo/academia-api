"""Modo cuarentena de facturación.

Con User.modo_cuarentena activo, todo documento nuevo nace en estado
"cuarentena": sin número (se muestra "Provisional"), sin envío y sin Drive.
Se puede abrir, eliminar y juntar con otro del mismo pagador. "Confirmar"
asigna los números definitivos (misma lógica que hoy: _next_invoice_number /
tipo_doc_for_metodo) y deja el documento como "emitida", ya cerrado.

Los documentos de cuarentena no guardan PDF: se renderiza al vuelo con los
datos actuales de sus pagos (editar el pago = editar el documento).
"""
import threading

from django.db import transaction
from django.utils import timezone

from modules.pagos.constants import tipo_doc_for_metodo

from .invoice_service import (
    _next_invoice_number,
    render_documento_pdf,
    upload_to_drive,
    validate_combined_pagos,
)
from .models import Documento, Emisor

ESTADO = "cuarentena"
PROVISIONAL = "Provisional"


class CuarentenaError(ValueError):
    """Predictable client error (400/409), never a server fault."""


def render_provisional_pdf(doc) -> bytes:
    pdf_bytes, _fecha, _emisor = render_documento_pdf(
        doc, watermark="PROVISIONAL", num_doc=PROVISIONAL, tipo=doc.tipo
    )
    return pdf_bytes


def crear_documento_cuarentena(tenant, pagos, emisor_id=None):
    """Create one provisional Documento for `pagos` (one pago, or several of
    the same pagador for a combined/family one). Idempotent per pago: if the
    primary pago already has a quarantined document, return it. No número is
    allocated and no counter is touched. Returns (doc, created)."""
    primary = pagos[0]
    existing = primary.documentos.filter(estado=ESTADO).order_by("-created_at").first()
    if existing and len(pagos) == 1:
        return existing, False

    if len(pagos) > 1:
        for p in pagos:
            if p.documentos.filter(estado=ESTADO).exists() or p.documentos_combinados.filter(estado=ESTADO).exists():
                raise CuarentenaError(
                    f"El pago {p.id} ya está en cuarentena: usa «Juntar» para combinar documentos en cuarentena."
                )
        emisor = validate_combined_pagos(pagos, emisor_id)
    else:
        if primary.estado_carga == "pendiente_completar" or not primary.alumno_id:
            raise CuarentenaError(f"Pago {primary.id} está incompleto — complétalo antes de generar factura/recibo.")
        emisor = primary.emisor
        if emisor is None:
            raise CuarentenaError(f"Pago {primary.id} no tiene emisor asignado.")

    doc = Documento.objects.create(
        academia=tenant,
        pago=primary,
        emisor=emisor,
        tipo=tipo_doc_for_metodo(primary.metodo),
        nombre=f"provisional-{primary.id}.pdf",
        num_doc="",
        estado=ESTADO,
    )
    if len(pagos) > 1:
        doc.pagos_adicionales.set(pagos[1:])
    return doc, True


def juntar_documentos(docs, emisor_id=None):
    """Merge several quarantined documents of the same pagador into the first
    one (oldest), which becomes the combined/family document (Bono Familia).
    The others are deleted — they have no número, so no gap. Returns the
    surviving Documento."""
    docs = sorted(docs, key=lambda d: (d.created_at, d.id))
    if len(docs) < 2:
        raise CuarentenaError("Selecciona al menos 2 documentos para juntar.")
    if any(d.estado != ESTADO for d in docs):
        raise CuarentenaError("Solo se pueden juntar documentos en cuarentena.")

    pagos = []
    for d in docs:
        for p in d.todos_los_pagos():
            if p.id not in {x.id for x in pagos}:
                pagos.append(p)

    # Validación estándar de combinados (mismo pagador, completos, emisor).
    # Los propios documentos de cuarentena que se van a fusionar no deben
    # bloquearse a sí mismos, así que se comprueba sin ellos.
    ids = [d.id for d in docs]
    _check_pagos_free_of_other_docs(pagos, ids)
    emisor = _resolve_emisor_for_merge(pagos, docs, emisor_id)

    with transaction.atomic():
        keep, rest = docs[0], docs[1:]
        keep.emisor = emisor
        keep.tipo = tipo_doc_for_metodo(pagos[0].metodo)
        keep.pago = pagos[0]
        keep.nombre = f"provisional-{pagos[0].id}.pdf"
        keep.save(update_fields=["emisor", "tipo", "pago", "nombre"])
        for d in rest:
            d.pagos_adicionales.clear()
            d.delete()
        keep.pagos_adicionales.set(pagos[1:])
    return keep


def _check_pagos_free_of_other_docs(pagos, own_doc_ids):
    for p in pagos:
        others = p.documentos.exclude(id__in=own_doc_ids).exclude(estado="borrador")
        others_c = p.documentos_combinados.exclude(id__in=own_doc_ids).exclude(estado="borrador")
        if others.exists() or others_c.exists():
            raise CuarentenaError(f"Pago {p.id} ya tiene otro documento — no se puede juntar.")


def _resolve_emisor_for_merge(pagos, docs, emisor_id):
    pagador_ids = {p.pagador_id for p in pagos}
    if len(pagador_ids) != 1 or None in pagador_ids:
        raise CuarentenaError("Todos los documentos deben tener el mismo pagador para juntarlos.")
    for p in pagos:
        if p.estado_carga == "pendiente_completar" or not p.alumno_id:
            raise CuarentenaError(f"Pago {p.id} está incompleto — complétalo antes de juntar.")
    if emisor_id:
        try:
            return Emisor.objects.get(id=emisor_id, academia=docs[0].academia)
        except Emisor.DoesNotExist:
            raise CuarentenaError(f"Emisor {emisor_id} no encontrado.")
    emisor_ids = {(d.emisor_id or (d.pago.emisor_id if d.pago else None)) for d in docs}
    if len(emisor_ids) != 1 or None in emisor_ids:
        raise CuarentenaError(
            "Estos documentos tienen emisores distintos (marcas distintas) — "
            "indica explícitamente qué emisora factura a esta familia."
        )
    return Emisor.objects.get(id=emisor_ids.pop())


def confirmar_documentos(tenant, doc_ids, scope_qs=None):
    """Assign definitive números to quarantined documents and issue them.

    All-or-nothing in one transaction: Documento rows and the affected Emisor
    rows are locked with select_for_update() (Emisores in pk order, so two
    concurrent confirmations can't deadlock), and números are handed out in
    creation order (created_at, id) so the result is correlative and in order.
    If anything fails — including rendering a PDF — the transaction rolls back
    and no counter moves, so a failed confirmation never leaves a gap.

    Returns (docs, finalizers): `finalizers` are callables to run *after* the
    transaction has committed (Drive upload, Sheets log).
    """
    doc_ids = list(dict.fromkeys(doc_ids))
    if not doc_ids:
        raise CuarentenaError("No hay documentos que confirmar.")

    qs = scope_qs if scope_qs is not None else Documento.objects.filter(academia=tenant)
    allowed = set(qs.filter(id__in=doc_ids).values_list("id", flat=True))
    if allowed != set(doc_ids):
        raise CuarentenaError("Alguno de los documentos no existe.")

    finalizers = []
    with transaction.atomic():
        docs = list(
            Documento.objects.select_for_update()
            .filter(id__in=doc_ids)
            .select_related("pago", "pago__alumno", "pago__pagador", "pago__grupo", "pago__emisor", "emisor")
            .order_by("created_at", "id")
        )
        # State is checked *after* taking the lock: a concurrent confirmation
        # that won the race has already flipped these to "emitida".
        not_q = [d for d in docs if d.estado != ESTADO]
        if not_q:
            raise CuarentenaError(
                "Estos documentos ya no están en cuarentena (¿otra persona los confirmó?): "
                + ", ".join(str(d.id) for d in not_q)
            )

        emisor_pks = sorted({(d.emisor_id or d.pago.emisor_id) for d in docs if d.pago})
        locked = {e.pk: e for e in Emisor.objects.select_for_update().filter(pk__in=emisor_pks).order_by("pk")}

        now = timezone.now()
        for d in docs:
            if d.pago is None:
                raise CuarentenaError(f"Documento {d.id} no tiene pago asociado.")
            emisor = locked[d.emisor_id or d.pago.emisor_id]
            tipo = tipo_doc_for_metodo(d.pago.metodo)
            pagos = d.todos_los_pagos()

            # A pre-assigned number (external reconciliation / bulk import) is
            # honoured exactly as the immediate flow does.
            num_doc = d.pago.numero_factura_reservado or _next_invoice_number(emisor, tipo)

            pdf_bytes, fecha, emisor_obj = render_documento_pdf(d, num_doc=num_doc, tipo=tipo)

            d.tipo = tipo
            d.num_doc = num_doc
            d.nombre = f"{num_doc}.pdf"
            d.pdf_data = pdf_bytes
            d.estado = "emitida"
            d.emitida_at = now
            d.save(update_fields=["tipo", "num_doc", "nombre", "pdf_data", "estado", "emitida_at"])

            for p in pagos:
                p.num_doc = num_doc
                p.numero_factura_reservado = num_doc
            type(pagos[0]).objects.bulk_update(pagos, ["num_doc", "numero_factura_reservado"])

            finalizers.append(_make_finalizer(d.id, pdf_bytes, f"{num_doc}.pdf", fecha, emisor_obj))
    return docs, finalizers


def _make_finalizer(doc_id, pdf_bytes, filename, fecha, emisor):
    import os

    folder_id = emisor.drive_folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID") or ""

    def run():
        def _drive():
            try:
                drive_id = upload_to_drive(pdf_bytes, filename, fecha.year, fecha.month, folder_id)
                Documento.objects.filter(pk=doc_id).update(s3_key=drive_id)
            except Exception as e:
                print(f"[cuarentena] background Drive upload failed for documento {doc_id}: {e}")

        threading.Thread(target=_drive, daemon=True).start()
        try:
            from .sheets_log import log_emision
            log_emision(Documento.objects.get(pk=doc_id))
        except Exception as e:
            print(f"[cuarentena] sheet log failed (non-critical): {e}")

    return run
