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
        codigo = serializer.validated_data.get("codigo") or self._next_codigo()
        serializer.save(academia=self.request.user.tenant, codigo=codigo)

    def _next_codigo(self):
        # Simple "P{n}" sequence per tenant — fine at this scale (a handful of
        # teachers, created one at a time through the UI, not a bulk-import
        # path); no locking, so a genuine simultaneous double-create could in
        # theory hand out the same number, same tradeoff as Profesor.orden.
        existing = Profesor.objects.filter(academia=self.request.user.tenant).count()
        return f"P{existing + 1}"
