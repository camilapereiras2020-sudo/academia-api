from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

TIPO_CHOICES = [
    ("factura", "Factura"),
    ("recibo", "Recibo"),
    ("recibo_efectivo", "Recibo (efectivo)"),
    ("otro", "Otro"),
]

ESTADO_CHOICES = [
    ("borrador", "Borrador"),
    ("emitida", "Emitida"),
    ("anulada", "Anulada"),
    ("rectificada", "Rectificada"),
]


class Emisor(models.Model):
    academia         = models.ForeignKey(User, on_delete=models.CASCADE, related_name="emisores")
    slug             = models.SlugField(max_length=50, unique=True)
    nombre           = models.CharField(max_length=200)
    autonoma         = models.CharField(max_length=200)
    nif              = models.CharField(max_length=20)
    direccion        = models.CharField(max_length=300)
    ciudad           = models.CharField(max_length=200)
    telefono         = models.CharField(max_length=20, blank=True)
    email            = models.CharField(max_length=200, blank=True)
    iban             = models.CharField(max_length=34, blank=True)
    factura_prefix   = models.CharField(max_length=10, default="CC")
    recibo_prefix    = models.CharField(max_length=10, default="RE")
    factura_baseline = models.IntegerField(default=0)
    recibo_baseline  = models.IntegerField(default=0)
    # Legacy cash ("efectivo") sequence — historical-only. Cash receipts used
    # to get their own isolated NUMBER+suffix sequence (e.g. "200C"), separate
    # from the recibo bucket. As of the numbering redesign, "efectivo" folds
    # into the same recibo_counter as everything else (see
    # pagos.constants.tipo_doc_for_metodo); these two fields are kept only so
    # already-issued "NNNC"/"NNNR" documents remain readable — nothing new is
    # ever numbered through them.
    recibo_efectivo_suffix   = models.CharField(max_length=5, blank=True, default="")
    recibo_efectivo_baseline = models.IntegerField(default=0)
    # Atomic counters (numbering redesign, replaces the old DB-scan-based
    # allocation in invoice_service._next_invoice_number). Each holds the
    # last number issued for this Emisor+tipo *this calendar year* —
    # *_counter_year tracks which year that is, so the sequence still resets
    # to baseline every January like the old suffix-filtered scan did.
    factura_counter      = models.IntegerField(default=0)
    factura_counter_year = models.IntegerField(null=True, blank=True)
    recibo_counter       = models.IntegerField(default=0)
    recibo_counter_year  = models.IntegerField(null=True, blank=True)
    drive_folder_id  = models.CharField(max_length=200, blank=True)
    activo           = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Documento(models.Model):
    academia = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="documentos"
    )
    pago = models.ForeignKey(
        "pagos.Pago",
        # PROTECT, not CASCADE: an issued Documento must never be silently
        # deleted just because its Pago was. PagoViewSet.destroy() already
        # blocks deleting a Pago with issued documents, but that guard only
        # covers that one code path — PROTECT enforces it at the DB level
        # for every path (shell, admin, management commands, ...).
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documentos",
    )
    tipo       = models.CharField(max_length=20, choices=TIPO_CHOICES)
    nombre     = models.CharField(max_length=200)
    num_doc    = models.CharField(max_length=30, blank=True)
    s3_key     = models.CharField(max_length=500, blank=True)
    local_path = models.CharField(max_length=500, blank=True)
    # Authoritative copy of the rendered PDF, stored in the DB at generation
    # time — independent of Google Drive. s3_key is filled in afterward by a
    # background upload (best-effort, never blocks/fails generation); until
    # then, and even if that upload never succeeds, this field alone is
    # enough to serve the document for download.
    pdf_data   = models.BinaryField(null=True, blank=True, editable=False)
    mime_type  = models.CharField(max_length=100, default="application/pdf")
    created_at = models.DateTimeField(auto_now_add=True)

    estado           = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="borrador")
    emitida_at       = models.DateTimeField(null=True, blank=True)
    anulada_at       = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.nombre

    @property
    def is_issued(self) -> bool:
        """True if this document was ever actually uploaded/sent — never hard-deletable."""
        return (
            self.estado != "borrador"
            or bool(self.s3_key)
            or bool(self.local_path)
            or bool(self.pdf_data)
        )
