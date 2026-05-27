
from rest_framework.routers import DefaultRouter
from .views import EmpresaViewSet, ContactoEmpresaViewSet

router = DefaultRouter()
router.register("empresas", EmpresaViewSet, basename="empresa")
router.register("contactos-empresa", ContactoEmpresaViewSet, basename="contacto-empresa")

urlpatterns = router.urls
