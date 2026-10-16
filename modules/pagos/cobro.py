"""El cobro (que el dinero haya llegado) es una decisión explícita, separada del
documento: anular un recibo o factura no decide por sí solo si el ingreso se
mantiene. Ver Pago.estado == "anulado"."""
from django.utils import timezone

PREGUNTA = "Indica si se ha cobrado este dinero (anular_cobro: true o false)."


def leer_bool(valor):
    """True/False si el valor es un booleano explícito ("true", "no"...); None si falta o no vale."""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        v = valor.strip().lower()
        if v in ("true", "1", "si", "sí"):
            return True
        if v in ("false", "0", "no"):
            return False
    return None


def anular_cobro(pagos, user, motivo):
    """Pasa los pagos a "anulado" (dejan de contar como ingreso en todas partes).
    No borra nada: queda quién, cuándo y por qué. Devuelve cuántos cambió."""
    ahora = timezone.now()
    cambiados = 0
    for p in pagos:
        if p.estado == "anulado":
            continue
        p.estado = "anulado"
        p.anulado_at = ahora
        p.motivo_anulacion = motivo
        p.anulado_por = user
        p.save(update_fields=["estado", "anulado_at", "motivo_anulacion", "anulado_por"])
        cambiados += 1
    return cambiados
