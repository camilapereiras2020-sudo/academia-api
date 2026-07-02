from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()


class Alumno(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alumnos")
    nombre = models.CharField(max_length=200)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    aviso_cumple_dias = models.PositiveIntegerField(null=True, blank=True)
    grupo = models.ForeignKey(
        "grupos.Grupo", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="alumnos"
    )
    pagador = models.ForeignKey(
        "pagadores.Pagador", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="alumnos"
    )
    empresa = models.ForeignKey(
        "empresas.Empresa", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="alumnos"
    )
    es_fundae = models.BooleanField(default=False)
    nivel = models.CharField(max_length=10, blank=True)
    notas = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
