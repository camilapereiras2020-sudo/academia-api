from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import AvisoViewSet, EquipoListView

router = DefaultRouter()
router.register(r"", AvisoViewSet, basename="aviso")

urlpatterns = [
    path("equipo/", EquipoListView.as_view()),
] + router.urls
