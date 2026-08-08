import sys
import environ
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# True whenever the Django test runner is driving the process — used to hard-block
# any code path that would otherwise make a real external call (e.g. Google Sheets
# logging) if a test forgets to mock it, instead of silently hitting production.
TESTING = "test" in sys.argv

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*"])

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
    "modules.crm",
    "modules.placement_test",
    "modules.empresas",
    "modules.clases",
    "modules.tarifas",
    "modules.whatsapp_reply",
    "modules.dashboard",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
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

# Wide open only in local dev (any localhost port Vite happens to use) — in
# production this combined with CORS_ALLOW_CREDENTIALS=True let any origin
# read authenticated responses (django-cors-headers reflects the request's
# Origin back instead of using "*" once credentials are allowed), silently
# making CORS_ALLOWED_ORIGINS below dead code. Real requests only ever come
# from the Vercel frontend, so production is locked down to just that.
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[
    "https://academia-frontend-psi.vercel.app",
])
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[
    "https://academia-frontend-psi.vercel.app",
    "https://*.railway.app",
    "https://*.onrender.com",
])

AWS_ACCESS_KEY_ID       = env("MINIO_ACCESS_KEY",    default="")
AWS_SECRET_ACCESS_KEY   = env("MINIO_SECRET_KEY",    default="")
AWS_STORAGE_BUCKET_NAME = env("MINIO_BUCKET_NAME",   default="academia-docs")
AWS_S3_ENDPOINT_URL     = env("MINIO_ENDPOINT",      default="")
AWS_S3_USE_SSL          = env.bool("MINIO_USE_SSL",  default=False)
AWS_DEFAULT_ACL         = "private"
AWS_S3_FILE_OVERWRITE   = False

RESEND_API_KEY        = env("RESEND_API_KEY",        default="")
DEFAULT_FROM_EMAIL    = env("DEFAULT_FROM_EMAIL",    default="noreply@example.com")
STRIPE_SECRET_KEY     = env("STRIPE_SECRET_KEY",     default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

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
