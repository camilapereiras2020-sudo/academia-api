from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import ReadOnlyForReception
from .models import Profesor
from .serializers import ProfesorSerializer


class ProfesorViewSet(ModelViewSet):
    serializer_class = ProfesorSerializer
    permission_classes = [permissions.IsAuthenticated, ReadOnlyForReception]

    def get_queryset(self):
        qs = Profesor.objects.filter(academia=self.request.user.tenant)
        activo = self.request.query_params.get("activo")
        if activo is not None:
            qs = qs.filter(activo=activo.lower() == "true")
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user.tenant)
