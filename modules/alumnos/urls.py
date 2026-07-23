from rest_framework.routers import DefaultRouter
from .views import (
    AlumnoViewSet, FechaImportanteViewSet, NotaAlumnoViewSet, ConsentimientoAlumnoViewSet,
)
router = DefaultRouter()
router.register(r"fechas-importantes", FechaImportanteViewSet, basename="fecha-importante")
router.register(r"notas", NotaAlumnoViewSet, basename="nota-alumno")
router.register(r"consentimientos", ConsentimientoAlumnoViewSet, basename="consentimiento-alumno")
router.register(r"", AlumnoViewSet, basename="alumno")
urlpatterns = router.urls
