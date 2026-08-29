from rest_framework.routers import DefaultRouter
from .views import GrupoViewSet, AulaViewSet
router = DefaultRouter()
# Registered before the empty-prefix GrupoViewSet, same ordering reason as
# modules.alumnos.urls (fechas-importantes/notas/consentimientos before the
# catch-all alumno route) — otherwise "aulas/" would be swallowed as a Grupo pk.
router.register(r"aulas", AulaViewSet, basename="aula")
router.register(r"", GrupoViewSet, basename="grupo")
urlpatterns = router.urls
