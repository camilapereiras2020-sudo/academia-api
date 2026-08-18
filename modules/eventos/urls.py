from rest_framework.routers import DefaultRouter
from .views import EventoViewSet
router = DefaultRouter()
router.register(r"", EventoViewSet, basename="evento")
urlpatterns = router.urls
