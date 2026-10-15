from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import NotReception, marca_scope_for
from .models import Tarifa, CargoExtra
from .serializers import TarifaSerializer, CargoExtraSerializer


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


class CargoExtraViewSet(ModelViewSet):
    """Clases a mayores (refuerzo puntual) — CRUD simple, filtrable por
    ?alumno=<id> para la ficha del alumno. Precio siempre manual, cualquier
    rol autenticado puede cargarlo (igual que registrar un Pago)."""
    serializer_class = CargoExtraSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = CargoExtra.objects.filter(academia=self.request.user.tenant).select_related("alumno")
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(alumno__marca=scope)
        alumno_id = self.request.query_params.get("alumno")
        if alumno_id:
            qs = qs.filter(alumno_id=alumno_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user.tenant)
