from rest_framework.routers import DefaultRouter
from .views import LeadViewSet, InteraccionViewSet

router = DefaultRouter()
router.register("leads", LeadViewSet, basename="lead")
router.register("interacciones", InteraccionViewSet, basename="interaccion")

urlpatterns = router.urls
