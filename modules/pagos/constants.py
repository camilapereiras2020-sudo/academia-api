METODOS_FACTURA = {"bizum", "transferencia", "tarjeta", "online"}


def tipo_doc_for_metodo(metodo: str) -> str:
    """Single source of truth for which numbering bucket a Pago's payment
    method lands in. "efectivo" used to get its own isolated sequence (see
    Emisor.recibo_efectivo_* — now legacy/historical-only); the numbering
    redesign folds it into the same "recibo" bucket as domiciliacion and
    everything else that isn't factura-eligible.
    """
    metodo = (metodo or "").lower()
    if metodo in METODOS_FACTURA:
        return "factura"
    return "recibo"
