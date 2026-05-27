
from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()

FACTURACION_CHOICES = [
    ("global", "Factura global mensual"),
    ("por_alumno", "Factura por alumno"),
    ("fundae", "FUNDAE"),
    ("mixta", "Mixta"),
]

class Empresa(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="empresas")
    nombre = models.CharField(max_length=200)
    cif = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.TextField(blank=True)
    facturacion = models.CharField(max_length=20, choices=FACTURACION_CHOICES, default="global", blank=True)
    notas = models.TextField(blank=True)
    activa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class ContactoEmpresa(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="contactos")
    nombre = models.CharField(max_length=200, blank=True)
    cargo = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    notas = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} — {self.empresa.nombre}"
