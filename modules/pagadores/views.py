from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from .models import Pagador
from .serializers import PagadorSerializer

class PagadorViewSet(ModelViewSet):
    serializer_class = PagadorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Pagador.objects.filter(academia=self.request.user).prefetch_related("alumnos")

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)
