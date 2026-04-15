from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Alumno(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alumnos")
    nombre = models.CharField(max_length=200)
    fnac = models.DateField(null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    notas = models.TextField(blank=True)
    aviso_cumple_dias = models.PositiveIntegerField(null=True, blank=True)
    pagador = models.ForeignKey("pagadores.Pagador", on_delete=models.SET_NULL, null=True, blank=True, related_name="alumnos")
    grupos = models.ManyToManyField("grupos.Grupo", through="AlumnoGrupo", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

class AlumnoGrupo(models.Model):
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE)
    grupo = models.ForeignKey("grupos.Grupo", on_delete=models.CASCADE)
    horarios = models.JSONField(default=list)

    class Meta:
        unique_together = ("alumno", "grupo")
