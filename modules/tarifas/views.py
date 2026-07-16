from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
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
        scope = marca_scope_for(self.request.user)
        if scope:
            provided = serializer.validated_data.get("marca")
            if provided and provided != scope:
                raise PermissionDenied(f"Solo podés crear tarifas de la marca {scope}.")
            serializer.save(academia=self.request.user.tenant, marca=scope)
        else:
            serializer.save(academia=self.request.user.tenant)

    def perform_update(self, serializer):
        scope = marca_scope_for(self.request.user)
        if scope:
            provided = serializer.validated_data.get("marca")
            if provided and provided != scope:
                raise PermissionDenied(f"Solo podés editar tarifas de la marca {scope}.")
            serializer.save(marca=scope)
        else:
            serializer.save()
