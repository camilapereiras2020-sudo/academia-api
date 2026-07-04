from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from .models import Tarifa
from .serializers import TarifaSerializer


class TarifaViewSet(ModelViewSet):
    serializer_class = TarifaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Tarifa.objects.filter(academia=self.request.user)
        marca = self.request.query_params.get("marca")
        if marca:
            qs = qs.filter(marca=marca)
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)
