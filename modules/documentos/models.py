from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

TIPO_CHOICES = [("factura", "Factura"), ("recibo", "Recibo"), ("otro", "Otro")]

class Documento(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documentos")
    pago = models.ForeignKey("pagos.Pago", on_delete=models.CASCADE, null=True, blank=True, related_name="documentos")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    nombre = models.CharField(max_length=200)
    s3_key = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=100, default="application/pdf")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.nombre
