from django.db import models
from django.contrib.auth import get_user_model
from modules.tarifas.models import MARCA_CHOICES

User = get_user_model()

TIPO_CHOICES = [
    ("reunion", "Reunión"),
    ("feriado", "Feriado"),
]


class Evento(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="eventos")
    marca = models.CharField(max_length=20, choices=MARCA_CHOICES, blank=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    fecha = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.fecha} - {self.titulo}"
