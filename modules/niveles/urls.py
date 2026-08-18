from rest_framework.routers import DefaultRouter
from .views import NivelViewSet
router = DefaultRouter()
router.register(r"", NivelViewSet, basename="nivel")
urlpatterns = router.urls
