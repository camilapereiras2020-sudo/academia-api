from rest_framework.routers import DefaultRouter
from .views import PagadorViewSet
router = DefaultRouter()
router.register(r"", PagadorViewSet, basename="pagador")
urlpatterns = router.urls
