
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from .models import Empresa, ContactoEmpresa
from .serializers import EmpresaSerializer, EmpresaListSerializer, ContactoEmpresaSerializer


class EmpresaViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "list":
            return EmpresaListSerializer
        return EmpresaSerializer

    def get_queryset(self):
        return Empresa.objects.filter(academia=self.request.user)

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)

    @action(detail=True, methods=["get"], url_path="alumnos")
    def alumnos(self, request, pk=None):
        from modules.alumnos.serializers import AlumnoSerializer
        empresa = self.get_object()
        alumnos = empresa.alumnos.all()
        return Response(AlumnoSerializer(alumnos, many=True).data)


class ContactoEmpresaViewSet(ModelViewSet):
    serializer_class = ContactoEmpresaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = ContactoEmpresa.objects.filter(empresa__academia=self.request.user)
        empresa_id = self.request.query_params.get("empresa")
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        return qs
