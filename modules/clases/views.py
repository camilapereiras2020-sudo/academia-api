from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import NotReception, marca_scope_for
from .models import Tarea, TareaCompletada, NotaDificultad
from .serializers import TareaSerializer, NotaDificultadSerializer


class TareaViewSet(ModelViewSet):
    serializer_class = TareaSerializer
    permission_classes = [permissions.IsAuthenticated, NotReception]

    def get_queryset(self):
        qs = Tarea.objects.filter(academia=self.request.user.tenant).select_related("grupo")
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(grupo__marca=scope)
        grupo = self.request.query_params.get("grupo")
        alumno = self.request.query_params.get("alumno")
        if grupo:
            qs = qs.filter(grupo_id=grupo)
        if alumno:
            qs = qs.filter(completados__alumno_id=alumno)
        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user.tenant)

    @action(detail=False, methods=["get"], url_path="historial-alumno")
    def historial_alumno(self, request):
        alumno_id = request.query_params.get("alumno")
        completados = TareaCompletada.objects.filter(
            alumno_id=alumno_id, tarea__academia=request.user.tenant
        ).select_related("tarea", "tarea__grupo")
        scope = marca_scope_for(request.user)
        if scope:
            completados = completados.filter(tarea__grupo__marca=scope)
        data = [{
            "tarea_id": c.tarea.id, "titulo": c.tarea.titulo,
            "fecha_entrega": c.tarea.fecha_entrega, "grupo": c.tarea.grupo.nombre,
            "estado": c.estado, "nota": c.nota,
        } for c in completados]
        return Response(data)


class NotaDificultadViewSet(ModelViewSet):
    serializer_class = NotaDificultadSerializer
    permission_classes = [permissions.IsAuthenticated, NotReception]

    def get_queryset(self):
        qs = NotaDificultad.objects.filter(academia=self.request.user.tenant).select_related("grupo", "alumno")
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(grupo__marca=scope)
        grupo = self.request.query_params.get("grupo")
        alumno = self.request.query_params.get("alumno")
        if grupo:
            qs = qs.filter(grupo_id=grupo)
        if alumno:
            qs = qs.filter(alumno_id=alumno)
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user.tenant)

    @action(detail=False, methods=["get"], url_path="historial-alumno")
    def historial_alumno(self, request):
        alumno_id = request.query_params.get("alumno")
        notas = NotaDificultad.objects.filter(
            alumno_id=alumno_id, academia=request.user.tenant
        ).select_related("grupo").order_by("-fecha")
        scope = marca_scope_for(request.user)
        if scope:
            notas = notas.filter(grupo__marca=scope)
        data = [{
            "id": n.id, "tema": n.tema, "nota": n.nota, "fecha": n.fecha, "grupo": n.grupo.nombre,
        } for n in notas]
        return Response(data)
