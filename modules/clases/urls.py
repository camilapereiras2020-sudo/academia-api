from rest_framework.routers import DefaultRouter
from .views import TareaViewSet, NotaDificultadViewSet

router = DefaultRouter()
router.register("tareas", TareaViewSet, basename="tarea")
router.register("notas-dificultad", NotaDificultadViewSet, basename="nota-dificultad")

urlpatterns = router.urls
