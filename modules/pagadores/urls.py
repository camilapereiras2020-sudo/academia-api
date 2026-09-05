from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import PagadorViewSet, PagadorCalculadoraView

router = DefaultRouter()
router.register(r"", PagadorViewSet, basename="pagador")

# "calculadora/" registered before the empty-prefix PagadorViewSet — same
# ordering reason as modules.grupos.urls ("aulas/" before the catch-all
# Grupo route): DRF's router pk pattern would otherwise swallow it as
# pk="calculadora".
urlpatterns = [
    path("calculadora/", PagadorCalculadoraView.as_view(), name="pagador-calculadora"),
] + router.urls
