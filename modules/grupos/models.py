
from django.db import models
from django.contrib.auth import get_user_model
from modules.tarifas.models import MARCA_CHOICES
from modules.profesores.models import Profesor

User = get_user_model()

TIPO_COBRO_CHOICES = [
    ("mensual", "Mensualidad fija"),
    ("por_hora", "Por hora"),
]

class Grupo(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="grupos")
    marca = models.CharField(max_length=20, choices=MARCA_CHOICES, default="rangers_academy")
    nombre = models.CharField(max_length=200)
    nivel = models.CharField(max_length=50, blank=True)
    profesor = models.ForeignKey(
        Profesor, on_delete=models.SET_NULL, null=True, blank=True, related_name="grupos"
    )
    tipo_cobro = models.CharField(max_length=10, choices=TIPO_COBRO_CHOICES, default="mensual")
    tarifa = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    precio_hora = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    aula = models.CharField(max_length=100, blank=True)
    color_idx = models.PositiveSmallIntegerField(default=0)
    horarios = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Aula(models.Model):
    """A lightweight, purely-additive lookup for room names + short codes
    (A1, A2…). Grupo.aula stays the free-text field it always was — nothing
    that already reads/writes Grupo.aula changes — this just gives the
    "+ Nueva clase" flow a place to look up or assign a código per room name,
    same idea as Profesor.codigo.
    """
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="aulas")
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=20, blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["academia", "nombre"], name="unique_aula_por_academia_nombre")
        ]

    def __str__(self):
        return self.nombre
