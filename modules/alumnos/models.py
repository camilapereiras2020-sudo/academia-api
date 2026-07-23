from django.db import models
from django.contrib.auth import get_user_model
from modules.tarifas.models import MARCA_CHOICES
User = get_user_model()

NIVEL_OBJETIVO_CHOICES = [
    ("A1", "A1"), ("A2", "A2"), ("B1", "B1"),
    ("B2", "B2"), ("C1", "C1"), ("C2", "C2"),
]
EXAMEN_OBJETIVO_CHOICES = [
    ("KET", "KET"), ("PET", "PET"), ("FCE", "FCE"),
    ("CAE", "CAE"), ("CPE", "CPE"), ("ninguno", "Ninguno"),
]


class Alumno(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alumnos")
    nombre = models.CharField(max_length=200)
    marca = models.CharField(max_length=20, choices=MARCA_CHOICES, default="rangers_academy")
    fecha_nacimiento = models.DateField(null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    dni = models.CharField(max_length=20, blank=True)
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

    foto_url = models.CharField(max_length=500, blank=True)
    nivel_objetivo = models.CharField(max_length=5, choices=NIVEL_OBJETIVO_CHOICES, blank=True)
    examen_objetivo = models.CharField(max_length=10, choices=EXAMEN_OBJETIVO_CHOICES, blank=True)
    colegio_origen = models.CharField(max_length=200, blank=True)
    idioma_nativo = models.CharField(max_length=100, blank=True)
    contacto_emergencia_nombre = models.CharField(max_length=200, blank=True)
    contacto_emergencia_telefono = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class FechaImportante(models.Model):
    TIPO_CHOICES = [
        ("examen", "Examen"),
        ("revision_nivel", "Revisión de nivel"),
        ("inicio_curso", "Inicio de curso"),
        ("fin_curso", "Fin de curso"),
        ("otro", "Otro"),
    ]
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name="fechas_importantes")
    fecha = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.alumno} ({self.fecha})"


class NotaAlumno(models.Model):
    TIPO_CHOICES = [
        ("progreso", "Progreso"),
        ("reunion", "Reunión"),
        ("general", "General"),
    ]
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name="notas_registro")
    autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="notas_alumno")
    fecha = models.DateTimeField(auto_now_add=True)
    contenido = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="general")

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.alumno} ({self.fecha:%Y-%m-%d})"


class DatoSalud(models.Model):
    """Dato de categoría especial GDPR (salud de menores) — no introducir datos reales
    hasta completar el trabajo de LOPD/GDPR pendiente. Uso actual: solo datos ficticios
    de prueba."""
    alumno = models.OneToOneField(Alumno, on_delete=models.CASCADE, related_name="dato_salud")
    alergias = models.TextField(blank=True)
    condiciones_medicas = models.TextField(blank=True)
    medicacion = models.TextField(blank=True)

    def __str__(self):
        return f"Datos de salud — {self.alumno}"


class ConsentimientoAlumno(models.Model):
    TIPO_CHOICES = [
        ("autorizacion_imagen", "Autorización de imagen"),
        ("proteccion_datos", "Protección de datos"),
        ("matricula", "Matrícula"),
    ]
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name="consentimientos")
    tipo = models.CharField(max_length=25, choices=TIPO_CHOICES)
    firmado = models.BooleanField(default=False)
    fecha_firma = models.DateField(null=True, blank=True)
    documento_url = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["tipo"]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.alumno}"
