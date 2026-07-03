from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

ORIGEN_CHOICES = [
    ("telefono", "Teléfono"),
    ("whatsapp", "WhatsApp"),
    ("instagram", "Instagram"),
    ("facebook", "Facebook"),
    ("recomendacion", "Recomendación"),
    ("web", "Web"),
]

ETAPA_CHOICES = [
    ("nueva_consulta", "Nueva consulta"),
    ("pendiente_llamar", "Pendiente de llamar"),
    ("en_conversacion", "En conversación"),
    ("clase_prueba", "Clase de prueba programada"),
    ("matriculado", "Matriculado"),
    ("frio", "Frío"),
    ("archivado", "Archivado"),
]

OBJETIVO_CHOICES = [
    ("general", "General"),
    ("cambridge", "Cambridge"),
    ("ib", "IB"),
    ("adultos", "Adultos"),
]

TIPO_INTERACCION_CHOICES = [
    ("whatsapp", "WhatsApp"),
    ("llamada", "Llamada"),
    ("email", "Email"),
    ("reunion", "Reunión"),
    ("en_persona", "En persona"),
    ("otro", "Otro"),
]


class Lead(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leads")

    # Datos obligatorios
    # nombre_contacto es obligatorio salvo que es_adulto=True (validado en el serializer,
    # ya que blank=True aqui es necesario para permitir el caso condicional).
    nombre_contacto = models.CharField(max_length=200, blank=True)
    nombre_alumno = models.CharField(max_length=200)
    edad_alumno = models.PositiveIntegerField(null=True, blank=True)
    curso_escolar = models.CharField(max_length=50, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    objetivo = models.CharField(max_length=20, choices=OBJETIVO_CHOICES, default="general")

    # Adulto / autopago
    es_adulto = models.BooleanField(default=False)
    pagador_es_alumno = models.BooleanField(
        default=False,
        help_text="Si es_adulto=True y el alumno paga por si mismo, autocompleta el pagador con sus propios datos al matricular.",
    )

    # Datos opcionales
    email = models.EmailField(blank=True)
    nivel_estimado = models.CharField(max_length=10, blank=True)
    disponibilidad = models.TextField(blank=True)
    colegio = models.CharField(max_length=200, blank=True)
    necesidades_especiales = models.TextField(blank=True)
    origen = models.CharField(max_length=20, choices=ORIGEN_CHOICES, default="telefono")
    notas = models.TextField(blank=True)

    # Pipeline
    etapa = models.CharField(max_length=20, choices=ETAPA_CHOICES, default="nueva_consulta")
    proximo_seguimiento = models.DateField(null=True, blank=True)

    # Vinculo con alumno si se matricula
    alumno = models.OneToOneField(
        "alumnos.Alumno", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="lead"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.nombre_alumno} ({self.get_etapa_display()})"

    @property
    def horas_sin_mover(self):
        from django.utils import timezone
        delta = timezone.now() - self.updated_at
        return delta.total_seconds() / 3600


class Interaccion(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="interacciones")
    tipo = models.CharField(max_length=20, choices=TIPO_INTERACCION_CHOICES)
    fecha = models.DateTimeField(auto_now_add=True)
    resumen = models.TextField()
    proxima_accion = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.lead.nombre_alumno}"
