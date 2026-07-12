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
    # Cash ("efectivo") receipts get their own sequence, isolated from the
    # RE/RR recibo bucket: NUMBER + suffix, no year suffix (e.g. "200C").
    recibo_efectivo_suffix   = models.CharField(max_length=5, blank=True, default="")
    recibo_efectivo_baseline = models.IntegerField(default=0)
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
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="documentos",
    )
    tipo       = models.CharField(max_length=20, choices=TIPO_CHOICES)
    nombre     = models.CharField(max_length=200)
    num_doc    = models.CharField(max_length=30, blank=True)
    s3_key     = models.CharField(max_length=500, blank=True)
    local_path = models.CharField(max_length=500, blank=True)
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
        return self.estado != "borrador" or bool(self.s3_key) or bool(self.local_path)
