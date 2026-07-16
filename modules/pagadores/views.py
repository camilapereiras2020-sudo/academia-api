from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import NotReception, marca_scope_for
from modules.core.mixins import ContactableViaPagadorMixin
from .models import Pagador
from .serializers import PagadorSerializer


class PagadorViewSet(ContactableViaPagadorMixin, ModelViewSet):
    serializer_class = PagadorSerializer
    permission_classes = [permissions.IsAuthenticated, NotReception]

    def get_queryset(self):
        qs = Pagador.objects.filter(academia=self.request.user.tenant).prefetch_related("alumnos")
        scope = marca_scope_for(self.request.user)
        if scope:
            # A pagador with at least one child in the co_manager's marca is
            # visible in full (PagadorSerializer only exposes alumnos_count,
            # not a filtered list — the count intentionally includes any
            # siblings in the other marca too).
            qs = qs.filter(alumnos__marca=scope).distinct()
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user.tenant)
