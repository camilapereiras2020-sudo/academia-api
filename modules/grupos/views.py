from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import ReadOnlyForReception, marca_scope_for
from .models import Grupo
from .serializers import GrupoSerializer

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
        serializer.save(academia=self.request.user.tenant)
