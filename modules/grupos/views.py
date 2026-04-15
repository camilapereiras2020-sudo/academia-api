from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from .models import Grupo
from .serializers import GrupoSerializer

class GrupoViewSet(ModelViewSet):
    serializer_class = GrupoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Grupo.objects.filter(academia=self.request.user)

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)
