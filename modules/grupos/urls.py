from rest_framework.routers import DefaultRouter
from .views import GrupoViewSet
router = DefaultRouter()
router.register(r"", GrupoViewSet, basename="grupo")
urlpatterns = router.urls
