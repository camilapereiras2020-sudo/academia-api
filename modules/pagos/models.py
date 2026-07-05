from django.db import models
from django.contrib.auth import get_user_model
from modules.tarifas.models import MARCA_CHOICES

User = get_user_model()

ESTADO_CHOICES = [("pagado", "Pagado"), ("pendiente", "Pendiente"), ("parcial", "Pago parcial")]
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
