from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import NotReception, marca_scope_for
from .models import Sesion, RegistroAsistencia
from .serializers import SesionSerializer

class SesionViewSet(ModelViewSet):
    serializer_class = SesionSerializer
    permission_classes = [permissions.IsAuthenticated, NotReception]

    def get_queryset(self):
        qs = Sesion.objects.filter(academia=self.request.user.tenant).select_related("grupo")
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(grupo__marca=scope)
        grupo = self.request.query_params.get("grupo")
        mes = self.request.query_params.get("mes")
        alumno = self.request.query_params.get("alumno")
        if grupo: qs = qs.filter(grupo_id=grupo)
        if mes: qs = qs.filter(fecha__startswith=mes)
        if alumno: qs = qs.filter(registros__alumno_id=alumno)
        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user.tenant)

    @action(detail=False, methods=["get"], url_path="historial-alumno")
    def historial_alumno(self, request):
        alumno_id = request.query_params.get("alumno")
        registros = RegistroAsistencia.objects.filter(
            alumno_id=alumno_id, sesion__academia=request.user.tenant
        ).select_related("sesion", "sesion__grupo")
        scope = marca_scope_for(request.user)
        if scope:
            registros = registros.filter(sesion__grupo__marca=scope)
        data = [{"sesion_id": r.sesion.id, "fecha": r.sesion.fecha, "hora": r.sesion.hora, "grupo": r.sesion.grupo.nombre, "estado": r.estado, "nota": r.nota, "es_invitado": r.es_invitado} for r in registros]
        return Response(data)
