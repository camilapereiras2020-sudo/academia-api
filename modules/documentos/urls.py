from rest_framework.routers import DefaultRouter
from .views import DocumentoViewSet, EmisorViewSet
router = DefaultRouter()
router.register(r"emisores", EmisorViewSet, basename="emisor")
router.register(r"", DocumentoViewSet, basename="documento")
urlpatterns = router.urls
