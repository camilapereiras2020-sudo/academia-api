from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import marca_scope_for
from modules.grupos.models import Grupo
from modules.alumnos.models import Alumno
from .models import Sesion, RegistroAsistencia
from .serializers import SesionSerializer, RegistroSerializer

class SesionViewSet(ModelViewSet):
    serializer_class = SesionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Sesion.objects.filter(academia=self.request.user.tenant).select_related("grupo")
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(grupo__marca=scope)
        grupo = self.request.query_params.get("grupo")
        mes = self.request.query_params.get("mes")
        alumno = self.request.query_params.get("alumno")
        fecha = self.request.query_params.get("fecha")
        if grupo: qs = qs.filter(grupo_id=grupo)
        if mes: qs = qs.filter(fecha__startswith=mes)
        if alumno: qs = qs.filter(registros__alumno_id=alumno)
        if fecha: qs = qs.filter(fecha=fecha)
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

    @action(detail=False, methods=["post"], url_path="marcar")
    def marcar(self, request):
        """Marca rápida de un alumno para una clase+fecha, usada por la
        pantalla de Asistencia > Hoy. Crea la Sesion si todavía no existe
        para ese grupo+fecha (nadie tuvo que "abrir lista" antes), y crea o
        actualiza el registro de ese alumno puntual — no toca al resto de
        la clase."""
        tenant = request.user.tenant
        grupo_id = request.data.get("grupo")
        fecha = request.data.get("fecha")
        alumno_id = request.data.get("alumno")
        estado = request.data.get("estado")
        nota = request.data.get("nota", "")

        if not (grupo_id and fecha and alumno_id and estado):
            return Response({"error": "grupo, fecha, alumno y estado son obligatorios."}, status=400)
        if estado not in dict(RegistroAsistencia._meta.get_field("estado").choices):
            return Response({"error": "estado invalido."}, status=400)

        grupo = Grupo.objects.filter(academia=tenant, id=grupo_id).first()
        if not grupo:
            return Response({"error": "Grupo no encontrado."}, status=404)
        scope = marca_scope_for(request.user)
        if scope and grupo.marca != scope:
            return Response({"error": "Sin permiso sobre esta marca."}, status=403)
        alumno = Alumno.objects.filter(academia=tenant, id=alumno_id).first()
        if not alumno:
            return Response({"error": "Alumno no encontrado."}, status=404)

        sesion, _ = Sesion.objects.get_or_create(academia=tenant, grupo=grupo, fecha=fecha)
        registro, _ = RegistroAsistencia.objects.update_or_create(
            sesion=sesion, alumno=alumno, defaults={"estado": estado, "nota": nota}
        )
        return Response(RegistroSerializer(registro).data)
