from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Grupo(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="grupos")
    nombre = models.CharField(max_length=200)
    nivel = models.CharField(max_length=50, blank=True)
    tarifa = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    aula = models.CharField(max_length=100, blank=True)
    color_idx = models.PositiveSmallIntegerField(default=0)
    horarios = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
