from rest_framework.routers import DefaultRouter
from .views import ProfesorViewSet
router = DefaultRouter()
router.register(r"", ProfesorViewSet, basename="profesor")
urlpatterns = router.urls
