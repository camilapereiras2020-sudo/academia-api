from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import NotReception, marca_scope_for
from .models import Tarifa
from .serializers import TarifaSerializer


class TarifaViewSet(ModelViewSet):
    serializer_class = TarifaSerializer
    permission_classes = [permissions.IsAuthenticated, NotReception]

    def get_queryset(self):
        qs = Tarifa.objects.filter(academia=self.request.user.tenant)
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(marca=scope)
        marca = self.request.query_params.get("marca")
        if marca:
            qs = qs.filter(marca=marca)
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user.tenant)
