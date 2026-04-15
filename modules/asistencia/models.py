from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

ESTADO_CHOICES = [("present", "Presente"), ("absent", "Ausente"), ("makeup", "Recuperacion"), ("guest", "Invitado/Traslado")]

class Sesion(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sesiones")
    grupo = models.ForeignKey("grupos.Grupo", on_delete=models.CASCADE, related_name="sesiones")
    fecha = models.DateField()
    hora = models.TimeField(null=True, blank=True)
    notas = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-hora"]

    def __str__(self):
        return f"{self.grupo} - {self.fecha}"

class RegistroAsistencia(models.Model):
    sesion = models.ForeignKey(Sesion, on_delete=models.CASCADE, related_name="registros")
    alumno = models.ForeignKey("alumnos.Alumno", on_delete=models.CASCADE)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default="present")
    nota = models.CharField(max_length=200, blank=True)
    es_invitado = models.BooleanField(default=False)

    class Meta:
        unique_together = ("sesion", "alumno")
