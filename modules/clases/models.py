from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

ESTADO_TAREA_CHOICES = [
    ("pendiente", "Pendiente"),
    ("completada", "Completada"),
    ("parcial", "Parcial"),
    ("no_entregada", "No entregada"),
]


class Tarea(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tareas")
    grupo = models.ForeignKey("grupos.Grupo", on_delete=models.CASCADE, related_name="tareas")
    sesion = models.ForeignKey(
        "asistencia.Sesion", on_delete=models.SET_NULL, null=True, blank=True, related_name="tareas"
    )
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    fecha_asignada = models.DateField()
    fecha_entrega = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_entrega"]

    def __str__(self):
        return f"{self.titulo} ({self.grupo})"


class TareaCompletada(models.Model):
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, related_name="completados")
    alumno = models.ForeignKey("alumnos.Alumno", on_delete=models.CASCADE, related_name="tareas_completadas")
    estado = models.CharField(max_length=15, choices=ESTADO_TAREA_CHOICES, default="pendiente")
    nota = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ("tarea", "alumno")

    def __str__(self):
        return f"{self.alumno} — {self.tarea} ({self.estado})"


class NotaDificultad(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notas_dificultad")
    grupo = models.ForeignKey("grupos.Grupo", on_delete=models.CASCADE, related_name="notas_dificultad")
    alumno = models.ForeignKey("alumnos.Alumno", on_delete=models.CASCADE, related_name="notas_dificultad")
    tema = models.CharField(max_length=200)
    nota = models.TextField()
    fecha = models.DateField()
    sesion = models.ForeignKey(
        "asistencia.Sesion", on_delete=models.SET_NULL, null=True, blank=True, related_name="notas_dificultad"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-created_at"]

    def __str__(self):
        return f"{self.alumno} — {self.tema}"
