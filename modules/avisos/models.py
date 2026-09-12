from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Aviso(models.Model):
    """Two things share this one small model, distinguished by `fecha`:
    a calendar task (fecha set — shown on that day for the whole team) and
    a quick note to a teammate (fecha blank — shown as a pending notice for
    `para` until they dismiss it). `para` null on a task means it's not
    assigned to anyone in particular, just a shared reminder on the calendar.
    """
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="avisos")
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name="avisos_creados")
    para = models.ForeignKey(User, on_delete=models.CASCADE, related_name="avisos_recibidos", null=True, blank=True)
    titulo = models.CharField(max_length=200)
    fecha = models.DateField(null=True, blank=True)
    hecha = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha", "-created_at"]

    def __str__(self):
        return self.titulo
