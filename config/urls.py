from django.contrib import admin
from django.urls import path, include

API_PREFIX = "api/v1/"

urlpatterns = [
    path("admin/", admin.site.urls),
    path(API_PREFIX + "auth/",       include("modules.authentication.urls")),
    path(API_PREFIX + "alumnos/",    include("modules.alumnos.urls")),
    path(API_PREFIX + "pagadores/",  include("modules.pagadores.urls")),
    path(API_PREFIX + "grupos/",     include("modules.grupos.urls")),
    path(API_PREFIX + "asistencia/", include("modules.asistencia.urls")),
    path(API_PREFIX + "pagos/",      include("modules.pagos.urls")),
    path(API_PREFIX + "documentos/", include("modules.documentos.urls")),
    path("api/v1/", include("modules.crm.urls")),
    path("api/v1/", include("modules.placement_test.urls")),
    path("api/v1/", include("modules.empresas.urls")),
    path(API_PREFIX + "clases/", include("modules.clases.urls")),
]