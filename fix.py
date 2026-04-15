import os

# Fix settings.py first
settings_content = '''import environ
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost"])
DEBUG = True

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "storages",
]

LOCAL_APPS = [
    "modules.authentication",
    "modules.alumnos",
    "modules.pagadores",
    "modules.grupos",
    "modules.asistencia",
    "modules.pagos",
    "modules.documentos",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "authentication.User"

DATABASES = {
    "default": env.db("DATABASE_URL")
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
}

CORS_ALLOW_ALL_ORIGINS = True

AWS_ACCESS_KEY_ID = env("MINIO_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = env("MINIO_SECRET_KEY")
AWS_STORAGE_BUCKET_NAME = env("MINIO_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = env("MINIO_ENDPOINT")
AWS_S3_USE_SSL = env.bool("MINIO_USE_SSL", default=False)
AWS_DEFAULT_ACL = "private"
AWS_S3_FILE_OVERWRITE = False

RESEND_API_KEY = env("RESEND_API_KEY")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET")

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

LANGUAGE_CODE = "es-es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
'''

with open('config/settings.py', 'w', encoding='utf-8') as f:
    f.write(settings_content)
print('OK: config/settings.py')

files = {}

files['modules/alumnos/views.py'] = '''from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from .models import Alumno, AlumnoGrupo
from .serializers import AlumnoSerializer

class AlumnoViewSet(ModelViewSet):
    serializer_class = AlumnoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Alumno.objects.filter(academia=self.request.user).select_related("pagador")

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)

    @action(detail=False, methods=["get"], url_path="cumpleanos")
    def cumpleanos(self, request):
        from datetime import date
        dias = int(request.query_params.get("dias", 14))
        hoy = date.today()
        resultado = []
        for alumno in self.get_queryset().exclude(fnac=None):
            b = alumno.fnac
            next_bd = b.replace(year=hoy.year)
            if next_bd < hoy:
                next_bd = next_bd.replace(year=hoy.year + 1)
            diff = (next_bd - hoy).days
            if diff <= dias:
                resultado.append({"id": alumno.id, "nombre": alumno.nombre, "fnac": alumno.fnac, "dias": diff})
        return Response(sorted(resultado, key=lambda x: x["dias"]))

    @action(detail=True, methods=["post"], url_path="asignar-grupo")
    def asignar_grupo(self, request, pk=None):
        alumno = self.get_object()
        AlumnoGrupo.objects.update_or_create(
            alumno=alumno, grupo_id=request.data.get("grupo_id"),
            defaults={"horarios": request.data.get("horarios", [])},
        )
        return Response({"ok": True})
'''

files['modules/alumnos/serializers.py'] = '''from rest_framework import serializers
from .models import Alumno, AlumnoGrupo

class AlumnoGrupoSerializer(serializers.ModelSerializer):
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)

    class Meta:
        model = AlumnoGrupo
        fields = ["grupo", "grupo_nombre", "horarios"]

class AlumnoSerializer(serializers.ModelSerializer):
    grupos_detalle = AlumnoGrupoSerializer(source="alumnogrupo_set", many=True, read_only=True)

    class Meta:
        model = Alumno
        fields = ["id", "nombre", "fnac", "telefono", "email", "notas", "aviso_cumple_dias", "pagador", "grupos_detalle", "created_at"]
        read_only_fields = ["id", "created_at"]
'''

files['modules/pagadores/views.py'] = '''from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from .models import Pagador
from .serializers import PagadorSerializer

class PagadorViewSet(ModelViewSet):
    serializer_class = PagadorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Pagador.objects.filter(academia=self.request.user).prefetch_related("alumnos")

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)
'''

files['modules/pagadores/serializers.py'] = '''from rest_framework import serializers
from .models import Pagador

class PagadorSerializer(serializers.ModelSerializer):
    alumnos_count = serializers.IntegerField(source="alumnos.count", read_only=True)

    class Meta:
        model = Pagador
        fields = ["id", "nombre", "nif", "telefono", "email", "metodo", "frecuencia", "iban", "notas", "fnac", "aviso_cumple_dias", "alumnos_count", "created_at"]
        read_only_fields = ["id", "created_at", "alumnos_count"]
'''

files['modules/grupos/views.py'] = '''from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from .models import Grupo
from .serializers import GrupoSerializer

class GrupoViewSet(ModelViewSet):
    serializer_class = GrupoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Grupo.objects.filter(academia=self.request.user)

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)
'''

files['modules/grupos/serializers.py'] = '''from rest_framework import serializers
from .models import Grupo

class GrupoSerializer(serializers.ModelSerializer):
    alumnos_count = serializers.SerializerMethodField()

    class Meta:
        model = Grupo
        fields = ["id", "nombre", "nivel", "tarifa", "aula", "color_idx", "horarios", "alumnos_count", "created_at"]
        read_only_fields = ["id", "created_at", "alumnos_count"]

    def get_alumnos_count(self, obj):
        return obj.alumno_set.count()
'''

files['modules/asistencia/views.py'] = '''from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from .models import Sesion, RegistroAsistencia
from .serializers import SesionSerializer

class SesionViewSet(ModelViewSet):
    serializer_class = SesionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Sesion.objects.filter(academia=self.request.user).select_related("grupo")
        grupo = self.request.query_params.get("grupo")
        mes = self.request.query_params.get("mes")
        alumno = self.request.query_params.get("alumno")
        if grupo: qs = qs.filter(grupo_id=grupo)
        if mes: qs = qs.filter(fecha__startswith=mes)
        if alumno: qs = qs.filter(registros__alumno_id=alumno)
        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)

    @action(detail=False, methods=["get"], url_path="historial-alumno")
    def historial_alumno(self, request):
        alumno_id = request.query_params.get("alumno")
        registros = RegistroAsistencia.objects.filter(
            alumno_id=alumno_id, sesion__academia=request.user
        ).select_related("sesion", "sesion__grupo")
        data = [{"sesion_id": r.sesion.id, "fecha": r.sesion.fecha, "hora": r.sesion.hora, "grupo": r.sesion.grupo.nombre, "estado": r.estado, "nota": r.nota, "es_invitado": r.es_invitado} for r in registros]
        return Response(data)
'''

files['modules/asistencia/serializers.py'] = '''from rest_framework import serializers
from .models import Sesion, RegistroAsistencia

class RegistroSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.CharField(source="alumno.nombre", read_only=True)

    class Meta:
        model = RegistroAsistencia
        fields = ["id", "alumno", "alumno_nombre", "estado", "nota", "es_invitado"]

class SesionSerializer(serializers.ModelSerializer):
    registros = RegistroSerializer(many=True, read_only=True)
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)

    class Meta:
        model = Sesion
        fields = ["id", "grupo", "grupo_nombre", "fecha", "hora", "notas", "registros", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        registros_data = self.context["request"].data.get("registros", [])
        sesion = Sesion.objects.create(**validated_data)
        for r in registros_data:
            RegistroAsistencia.objects.create(sesion=sesion, **r)
        return sesion
'''

files['modules/pagos/views.py'] = '''from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.utils import timezone
from .models import Pago
from .serializers import PagoSerializer

class PagoViewSet(ModelViewSet):
    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Pago.objects.filter(academia=self.request.user).select_related("pagador", "alumno", "grupo")
        estado = self.request.query_params.get("estado")
        periodo = self.request.query_params.get("periodo")
        if estado: qs = qs.filter(estado=estado)
        if periodo: qs = qs.filter(periodo=periodo)
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)

    @action(detail=True, methods=["post"], url_path="marcar-pagado")
    def marcar_pagado(self, request, pk=None):
        pago = self.get_object()
        pago.estado = "pagado"
        pago.fecha = timezone.now().date()
        pago.save(update_fields=["estado", "fecha"])
        return Response(PagoSerializer(pago).data)

    @action(detail=True, methods=["post"], url_path="stripe-intent")
    def stripe_intent(self, request, pk=None):
        import stripe
        from django.conf import settings
        stripe.api_key = settings.STRIPE_SECRET_KEY
        pago = self.get_object()
        intent = stripe.PaymentIntent.create(amount=int(float(pago.total) * 100), currency="eur", metadata={"pago_id": pago.id})
        pago.stripe_payment_intent = intent.id
        pago.save(update_fields=["stripe_payment_intent"])
        return Response({"client_secret": intent.client_secret})
'''

files['modules/pagos/serializers.py'] = '''from rest_framework import serializers
from .models import Pago

class PagoSerializer(serializers.ModelSerializer):
    pagador_nombre = serializers.CharField(source="pagador.nombre", read_only=True)
    alumno_nombre = serializers.CharField(source="alumno.nombre", read_only=True)
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)

    class Meta:
        model = Pago
        fields = ["id", "pagador", "pagador_nombre", "alumno", "alumno_nombre", "grupo", "grupo_nombre", "periodo", "mensualidad", "descuento", "extras", "total", "metodo", "estado", "fecha", "notas", "num_doc", "serie_id", "iban", "stripe_payment_intent", "created_at"]
        read_only_fields = ["id", "created_at", "num_doc"]
'''

files['modules/documentos/views.py'] = '''from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework.viewsets import ModelViewSet
from .models import Documento
from .serializers import DocumentoSerializer
import uuid

class DocumentoViewSet(ModelViewSet):
    serializer_class = DocumentoSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        return Documento.objects.filter(academia=self.request.user)

    def create(self, request, *args, **kwargs):
        import boto3
        from botocore.config import Config
        from django.conf import settings
        file = request.FILES.get("file")
        nombre = request.data.get("nombre", file.name if file else "documento")
        tipo = request.data.get("tipo", "otro")
        pago_id = request.data.get("pago")
        client = boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL, aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, config=Config(signature_version="s3v4"), use_ssl=settings.AWS_S3_USE_SSL)
        key = f"{request.user.id}/{tipo}/{uuid.uuid4()}/{nombre}"
        client.upload_fileobj(file, settings.AWS_STORAGE_BUCKET_NAME, key, ExtraArgs={"ContentType": file.content_type})
        doc = Documento.objects.create(academia=request.user, pago_id=pago_id, tipo=tipo, nombre=nombre, s3_key=key, mime_type=file.content_type)
        return Response(DocumentoSerializer(doc).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        import boto3
        from botocore.config import Config
        from django.conf import settings
        doc = self.get_object()
        client = boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL, aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, config=Config(signature_version="s3v4"), use_ssl=settings.AWS_S3_USE_SSL)
        client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=doc.s3_key)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
'''

files['modules/documentos/serializers.py'] = '''from rest_framework import serializers
from .models import Documento

class DocumentoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Documento
        fields = ["id", "pago", "tipo", "nombre", "mime_type", "url", "created_at"]
        read_only_fields = ["id", "created_at", "url"]

    def get_url(self, obj):
        import boto3
        from botocore.config import Config
        from django.conf import settings
        client = boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL, aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, config=Config(signature_version="s3v4"), use_ssl=settings.AWS_S3_USE_SSL)
        return client.generate_presigned_url("get_object", Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": obj.s3_key}, ExpiresIn=3600)
'''

files['modules/authentication/views.py'] = '''from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import RegisterSerializer, UserProfileSerializer

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
'''

files['modules/authentication/serializers.py'] = '''from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "username", "password", "password2", "academia_nombre"]

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError("Las contrasenas no coinciden.")
        return data

    def create(self, validated_data):
        validated_data.pop("password2")
        return User.objects.create_user(**validated_data)

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "academia_nombre", "academia_nif", "academia_dir", "academia_tel", "academia_logo"]
        read_only_fields = ["id", "email"]
'''

files['modules/authentication/models.py'] = '''from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    email = models.EmailField(unique=True)
    academia_nombre = models.CharField(max_length=200, blank=True)
    academia_nif = models.CharField(max_length=20, blank=True)
    academia_dir = models.CharField(max_length=300, blank=True)
    academia_tel = models.CharField(max_length=20, blank=True)
    academia_logo = models.CharField(max_length=500, blank=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.email
'''

files['modules/alumnos/models.py'] = '''from django.db import models
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
'''

files['modules/pagadores/models.py'] = '''from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

METODO_CHOICES = [("efectivo", "Efectivo"), ("transferencia", "Transferencia"), ("bizum", "Bizum"), ("domiciliacion", "Domiciliacion"), ("tarjeta", "Tarjeta")]
FRECUENCIA_CHOICES = [("mensual", "Mensual"), ("por_clase", "Por clase"), ("trimestral", "Trimestral"), ("anual", "Anual")]

class Pagador(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pagadores")
    nombre = models.CharField(max_length=200)
    nif = models.CharField(max_length=20, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES, blank=True)
    frecuencia = models.CharField(max_length=20, choices=FRECUENCIA_CHOICES, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    notas = models.TextField(blank=True)
    fnac = models.DateField(null=True, blank=True)
    aviso_cumple_dias = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
'''

files['modules/grupos/models.py'] = '''from django.db import models
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
'''

files['modules/asistencia/models.py'] = '''from django.db import models
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
'''

files['modules/pagos/models.py'] = '''from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

ESTADO_CHOICES = [("pagado", "Pagado"), ("pendiente", "Pendiente"), ("parcial", "Pago parcial")]

class Pago(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pagos")
    pagador = models.ForeignKey("pagadores.Pagador", on_delete=models.PROTECT, related_name="pagos")
    alumno = models.ForeignKey("alumnos.Alumno", on_delete=models.PROTECT, related_name="pagos")
    grupo = models.ForeignKey("grupos.Grupo", on_delete=models.PROTECT, related_name="pagos")
    periodo = models.CharField(max_length=7)
    mensualidad = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    extras = models.JSONField(default=list)
    total = models.DecimalField(max_digits=8, decimal_places=2)
    metodo = models.CharField(max_length=20)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    fecha = models.DateField(null=True, blank=True)
    notas = models.TextField(blank=True)
    num_doc = models.CharField(max_length=30, blank=True)
    serie_id = models.CharField(max_length=10, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    stripe_payment_intent = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.num_doc} - {self.alumno} ({self.periodo})"
'''

files['modules/documentos/models.py'] = '''from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

TIPO_CHOICES = [("factura", "Factura"), ("recibo", "Recibo"), ("otro", "Otro")]

class Documento(models.Model):
    academia = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documentos")
    pago = models.ForeignKey("pagos.Pago", on_delete=models.CASCADE, null=True, blank=True, related_name="documentos")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    nombre = models.CharField(max_length=200)
    s3_key = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=100, default="application/pdf")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.nombre
'''

for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'OK: {path}')

print('\nTodo listo!')