METODOS_FACTURA = {"bizum", "transferencia", "tarjeta", "online"}


def tipo_doc_for_metodo(metodo: str) -> str:
    """Single source of truth for which numbering bucket a Pago's payment
    method lands in. "efectivo" gets its own sequence (see Emisor.recibo_efectivo_*),
    separate from the "recibo" bucket shared by domiciliacion and anything else.
    """
    metodo = (metodo or "").lower()
    if metodo in METODOS_FACTURA:
        return "factura"
    if metodo == "efectivo":
        return "recibo_efectivo"
    return "recibo"
