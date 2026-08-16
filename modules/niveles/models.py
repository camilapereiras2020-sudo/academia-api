from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

CATEGORIA_CHOICES = [
    ("kids", "Kids"),
    ("teens", "Teens"),
    ("adults", "Adults"),
]


class Nivel(models.Model):
    academia   = models.ForeignKey(User, on_delete=models.CASCADE, related_name="niveles")
    nombre     = models.CharField(max_length=100)
    categoria  = models.CharField(max_length=10, choices=CATEGORIA_CHOICES)
    orden      = models.PositiveIntegerField(default=0)
    activo     = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["categoria", "orden", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["academia", "categoria", "nombre"],
                name="unique_nivel_por_academia_categoria_nombre",
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.get_categoria_display()})"
