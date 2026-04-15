from rest_framework.routers import DefaultRouter
from .views import SesionViewSet
router = DefaultRouter()
router.register(r"", SesionViewSet, basename="sesion")
urlpatterns = router.urls
