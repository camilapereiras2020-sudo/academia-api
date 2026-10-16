from django.db import models
from django.contrib.auth import get_user_model
from modules.tarifas.models import MARCA_CHOICES

User = get_user_model()

# "anulado": el cobro se anuló (error o duplicado). No cuenta como ingreso en
# ninguna parte; se decide de forma explícita al anular un documento.
ESTADO_CHOICES = [("pagado", "Pagado"), ("pendiente", "Pendiente"), ("parcial", "Pago parcial"), ("anulado", "Anulado")]
ESTADO_CARGA_CHOICES = [("completo", "Completo"), ("pendiente_completar", "Pendiente de completar")]

class Pago(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pagos")
    marca = models.CharField(max_length=20, choices=MARCA_CHOICES, default="rangers_academy")
    pagador = models.ForeignKey("pagadores.Pagador", on_delete=models.PROTECT, related_name="pagos", null=True, blank=True)
    alumno = models.ForeignKey("alumnos.Alumno", on_delete=models.PROTECT, related_name="pagos", null=True, blank=True)
    grupo = models.ForeignKey(
        "grupos.Grupo",
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="pagos",
    )
    periodo = models.CharField(max_length=7)
    mensualidad = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    extras = models.JSONField(default=list)
    total = models.DecimalField(max_digits=8, decimal_places=2)
    metodo = models.CharField(max_length=20)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    # Rastro de un cobro anulado (quién, cuándo y por qué).
    anulado_at       = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True)
    anulado_por      = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # "Borrado": solo un pago con el cobro anulado. Se oculta de las listas pero
    # no se destruye, y sus documentos anulados se conservan (numeración fiscal).
    borrado_at  = models.DateTimeField(null=True, blank=True)
    borrado_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    fecha = models.DateField(null=True, blank=True)
    horas_trabajadas = models.DecimalField(max_digits=5, decimal_places=1, default=0, help_text='Horas trabajadas este mes')
    notas = models.TextField(blank=True)
    num_doc = models.CharField(max_length=30, blank=True)
    serie_id = models.CharField(max_length=10, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    stripe_payment_intent = models.CharField(max_length=100, blank=True)
    emisor = models.ForeignKey(
        "documentos.Emisor",
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="pagos",
    )
    tarifa = models.ForeignKey(
        "tarifas.Tarifa",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="pagos",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    estado_carga             = models.CharField(max_length=20, choices=ESTADO_CARGA_CHOICES, default="completo")
    numero_factura_reservado = models.CharField(max_length=30, blank=True)
    concepto_original        = models.CharField(max_length=300, blank=True)
    concepto_libre           = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.num_doc} - {self.alumno} ({self.periodo})"


class ConceptoAlias(models.Model):
    """Maps a recurring Bizum concepto_original phrase (or a nickname) to a
    specific Alumno and/or Pagador, checked first by matching.best_match()
    before falling back to token-based fuzzy matching.
    """
    academia   = models.ForeignKey(User, on_delete=models.CASCADE, related_name="concepto_alias")
    alias_text = models.CharField(max_length=100)
    alumno     = models.ForeignKey("alumnos.Alumno", on_delete=models.CASCADE, null=True, blank=True, related_name="concepto_alias")
    pagador    = models.ForeignKey("pagadores.Pagador", on_delete=models.CASCADE, null=True, blank=True, related_name="concepto_alias")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["alias_text"]
        unique_together = [("academia", "alias_text")]
        verbose_name = "Alias de concepto"
        verbose_name_plural = "Alias de concepto"

    def __str__(self):
        return self.alias_text
