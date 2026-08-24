from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Profesor(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="profesores")
    nombre = models.CharField(max_length=100)
    es_suplente = models.BooleanField(default=False)
    orden = models.PositiveSmallIntegerField(default=0)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["academia", "nombre"], name="unique_profesor_por_academia_nombre")
        ]

    def __str__(self):
        return self.nombre
