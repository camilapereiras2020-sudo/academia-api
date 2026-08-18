from django.db.models import Q
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import ReadOnlyForReception, marca_scope_for
from .models import Evento
from .serializers import EventoSerializer


class EventoViewSet(ModelViewSet):
    serializer_class = EventoSerializer
    permission_classes = [permissions.IsAuthenticated, ReadOnlyForReception]

    def get_queryset(self):
        qs = Evento.objects.filter(academia=self.request.user.tenant)
        scope = marca_scope_for(self.request.user)
        if scope:
            # Marca-scoped users also see academia-wide events (blank marca).
            qs = qs.filter(Q(marca=scope) | Q(marca=""))
        marca = self.request.query_params.get("marca")
        if marca:
            qs = qs.filter(marca=marca)
        desde = self.request.query_params.get("desde")
        if desde:
            qs = qs.filter(fecha__gte=desde)
        hasta = self.request.query_params.get("hasta")
        if hasta:
            qs = qs.filter(fecha__lte=hasta)
        return qs

    def perform_create(self, serializer):
        scope = marca_scope_for(self.request.user)
        if scope:
            provided = serializer.validated_data.get("marca")
            if provided and provided != scope:
                raise PermissionDenied(f"Solo podés crear eventos de la marca {scope}.")
            serializer.save(academia=self.request.user.tenant, marca=scope)
        else:
            serializer.save(academia=self.request.user.tenant)

    def perform_update(self, serializer):
        scope = marca_scope_for(self.request.user)
        if scope:
            provided = serializer.validated_data.get("marca")
            if provided and provided != scope:
                raise PermissionDenied(f"Solo podés editar eventos de la marca {scope}.")
            serializer.save(marca=scope)
        else:
            serializer.save()
