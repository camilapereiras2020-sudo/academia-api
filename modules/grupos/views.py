from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import ReadOnlyForReception, marca_scope_for
from .models import Grupo, Aula
from .serializers import GrupoSerializer, AulaSerializer

class GrupoViewSet(ModelViewSet):
    serializer_class = GrupoSerializer
    permission_classes = [permissions.IsAuthenticated, ReadOnlyForReception]

    def get_queryset(self):
        qs = Grupo.objects.filter(academia=self.request.user.tenant)
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(marca=scope)
        return qs

    def perform_create(self, serializer):
        scope = marca_scope_for(self.request.user)
        if scope:
            provided = serializer.validated_data.get("marca")
            if provided and provided != scope:
                raise PermissionDenied(f"Solo podés crear grupos de la marca {scope}.")
            serializer.save(academia=self.request.user.tenant, marca=scope)
        else:
            serializer.save(academia=self.request.user.tenant)

    def perform_update(self, serializer):
        scope = marca_scope_for(self.request.user)
        if scope:
            provided = serializer.validated_data.get("marca")
            if provided and provided != scope:
                raise PermissionDenied(f"Solo podés editar grupos de la marca {scope}.")
            serializer.save(marca=scope)
        else:
            serializer.save()


class AulaViewSet(ModelViewSet):
    serializer_class = AulaSerializer
    permission_classes = [permissions.IsAuthenticated, ReadOnlyForReception]

    def get_queryset(self):
        qs = Aula.objects.filter(academia=self.request.user.tenant)
        activo = self.request.query_params.get("activo")
        if activo is not None:
            qs = qs.filter(activo=activo.lower() == "true")
        return qs

    def perform_create(self, serializer):
        codigo = serializer.validated_data.get("codigo") or self._next_codigo()
        serializer.save(academia=self.request.user.tenant, codigo=codigo)

    def _next_codigo(self):
        # Same simple per-tenant sequence as Profesor.codigo — see that
        # viewset's _next_codigo for the tradeoff note.
        existing = Aula.objects.filter(academia=self.request.user.tenant).count()
        return f"A{existing + 1}"
