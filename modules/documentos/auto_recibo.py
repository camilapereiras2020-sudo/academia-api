"""Recibo automático: al registrar un pago como cobrado se crea su recibo
(provisional, en cuarentena). La factura nunca es automática: se genera a mano
desde un recibo confirmado (cuarentena.crear_factura_desde_recibo).

Es tolerante a fallos: si no se puede crear (pago incompleto, sin emisor…) el
pago se guarda igual y se registra el motivo — registrar un cobro nunca debe
fallar por culpa del documento.
"""
import logging

from django.db import transaction

from . import cuarentena
from .models import Documento

logger = logging.getLogger(__name__)


def _documentos_de(pago):
    return list(pago.documentos.all()) + list(pago.documentos_combinados.all())


def tiene_documento_vigente(pago):
    return any(d.estado not in ("borrador", "anulada") for d in _documentos_de(pago))


def _es_bono_familia(pago):
    from modules.tarifas.pricing import calcular_cuota_alumno

    try:
        return calcular_cuota_alumno(pago.alumno)["tipo"] == "bono_familia"
    except Exception:
        return False


def _recibo_provisional_de_la_familia(pago):
    """Bono Familia: un único recibo combinado. Si algún hermano ya tiene su
    recibo todavía provisional (mismo pagador, periodo y emisor), el pago se une
    a él; uno ya confirmado no se puede ampliar."""
    if not pago.pagador_id or not _es_bono_familia(pago):
        return None
    return (
        Documento.objects.filter(
            academia=pago.academia, estado=cuarentena.ESTADO, tipo="recibo", recibo_origen__isnull=True,
            pago__pagador_id=pago.pagador_id, pago__periodo=pago.periodo, pago__emisor_id=pago.emisor_id,
        )
        .order_by("created_at", "id")
        .first()
    )


def asegurar_recibo(pago):
    """Crea (o completa) el recibo provisional de un pago cobrado. Devuelve el
    Documento, o None si no corresponde o no se pudo (nunca lanza)."""
    from modules.pagos.models import Pago

    if pago.estado != "pagado" or pago.estado_carga != "completo" or not pago.alumno_id or not pago.emisor_id:
        return None
    try:
        with transaction.atomic():
            pago = Pago.objects.select_for_update().select_related("alumno", "pagador", "emisor", "academia").get(pk=pago.pk)
            if tiene_documento_vigente(pago):
                return None
            hermano = _recibo_provisional_de_la_familia(pago)
            if hermano is not None:
                hermano.pagos_adicionales.add(pago)
                return hermano
            doc, _ = cuarentena.crear_documento_cuarentena(pago.academia, [pago])
            return doc
    except Exception:
        logger.exception("No se pudo crear el recibo automático del pago %s", getattr(pago, "pk", "?"))
        return None
