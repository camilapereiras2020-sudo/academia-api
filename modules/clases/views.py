from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from .models import Tarea, TareaCompletada, NotaDificultad
from .serializers import TareaSerializer, NotaDificultadSerializer


class TareaViewSet(ModelViewSet):
    serializer_class = TareaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Tarea.objects.filter(academia=self.request.user).select_related("grupo")
        grupo = self.request.query_params.get("grupo")
        alumno = self.request.query_params.get("alumno")
        if grupo:
            qs = qs.filter(grupo_id=grupo)
        if alumno:
            qs = qs.filter(completados__alumno_id=alumno)
        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)

    @action(detail=False, methods=["get"], url_path="historial-alumno")
    def historial_alumno(self, request):
        alumno_id = request.query_params.get("alumno")
        completados = TareaCompletada.objects.filter(
            alumno_id=alumno_id, tarea__academia=request.user
        ).select_related("tarea", "tarea__grupo")
        data = [{
            "tarea_id": c.tarea.id, "titulo": c.tarea.titulo,
            "fecha_entrega": c.tarea.fecha_entrega, "grupo": c.tarea.grupo.nombre,
            "estado": c.estado, "nota": c.nota,
        } for c in completados]
        return Response(data)


class NotaDificultadViewSet(ModelViewSet):
    serializer_class = NotaDificultadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = NotaDificultad.objects.filter(academia=self.request.user).select_related("grupo", "alumno")
        grupo = self.request.query_params.get("grupo")
        alumno = self.request.query_params.get("alumno")
        if grupo:
            qs = qs.filter(grupo_id=grupo)
        if alumno:
            qs = qs.filter(alumno_id=alumno)
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)

    @action(detail=False, methods=["get"], url_path="historial-alumno")
    def historial_alumno(self, request):
        alumno_id = request.query_params.get("alumno")
        notas = NotaDificultad.objects.filter(
            alumno_id=alumno_id, academia=request.user
        ).select_related("grupo").order_by("-fecha")
        data = [{
            "id": n.id, "tema": n.tema, "nota": n.nota, "fecha": n.fecha, "grupo": n.grupo.nombre,
        } for n in notas]
        return Response(data)
