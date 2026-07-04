from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

NOMBRE_CHOICES = [
    ("clase_grupo", "Clase Grupo"),
    ("bono_familia", "Bono Familia"),
    ("clase_privada", "Clase Privada"),
    ("clase_recuperada", "Clase Recuperada"),
]

TIPO_COBRO_CHOICES = [
    ("por_hora", "Por hora"),
    ("mensual", "Mensual"),
    ("bono_familiar", "Bono familiar"),
]

MARCA_CHOICES = [
    ("cami_and_co", "Cami & Co"),
    ("rangers_academy", "Rangers Academy"),
]

HORAS_SEMANALES_CHOICES = [(1, "1"), (2, "2"), (3, "3")]


class Tarifa(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tarifas")
    nombre = models.CharField(max_length=20, choices=NOMBRE_CHOICES)
    tipo_cobro = models.CharField(max_length=20, choices=TIPO_COBRO_CHOICES)
    marca = models.CharField(max_length=20, choices=MARCA_CHOICES)
    precio = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    horas_semanales = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=HORAS_SEMANALES_CHOICES
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["marca", "nombre", "horas_semanales"]

    def __str__(self):
        horas = f" ({self.horas_semanales}h/sem)" if self.horas_semanales else ""
        return f"{self.get_marca_display()} - {self.get_nombre_display()}{horas}"
