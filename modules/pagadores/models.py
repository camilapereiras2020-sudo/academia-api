from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

METODO_CHOICES = [("efectivo", "Efectivo"), ("transferencia", "Transferencia"), ("bizum", "Bizum"), ("domiciliacion", "Domiciliacion"), ("tarjeta", "Tarjeta")]
FRECUENCIA_CHOICES = [("mensual", "Mensual"), ("por_clase", "Por clase"), ("trimestral", "Trimestral"), ("anual", "Anual")]

class Pagador(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pagadores")
    nombre = models.CharField(max_length=200)
    nif = models.CharField(max_length=20, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=300, blank=True)
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES, blank=True)
    frecuencia = models.CharField(max_length=20, choices=FRECUENCIA_CHOICES, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    notas = models.TextField(blank=True)
    fnac = models.DateField(null=True, blank=True)
    aviso_cumple_dias = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
