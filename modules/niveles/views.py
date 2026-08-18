from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import ReadOnlyForReception
from .models import Nivel
from .serializers import NivelSerializer


class NivelViewSet(ModelViewSet):
    serializer_class = NivelSerializer
    permission_classes = [permissions.IsAuthenticated, ReadOnlyForReception]

    def get_queryset(self):
        qs = Nivel.objects.filter(academia=self.request.user.tenant)
        categoria = self.request.query_params.get("categoria")
        if categoria:
            qs = qs.filter(categoria=categoria)
        activo = self.request.query_params.get("activo")
        if activo is not None:
            qs = qs.filter(activo=activo.lower() == "true")
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user.tenant)
