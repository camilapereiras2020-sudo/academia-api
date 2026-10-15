from rest_framework.routers import DefaultRouter
from .views import TarifaViewSet, CargoExtraViewSet
router = DefaultRouter()
router.register(r"cargos-extra", CargoExtraViewSet, basename="cargo-extra")
router.register(r"", TarifaViewSet, basename="tarifa")
urlpatterns = router.urls
