from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from .models import Alumno, AlumnoGrupo
from .serializers import AlumnoSerializer

class AlumnoViewSet(ModelViewSet):
    serializer_class = AlumnoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Alumno.objects.filter(academia=self.request.user).select_related("pagador")

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)

    @action(detail=False, methods=["get"], url_path="cumpleanos")
    def cumpleanos(self, request):
        from datetime import date
        dias = int(request.query_params.get("dias", 14))
        hoy = date.today()
        resultado = []
        for alumno in self.get_queryset().exclude(fnac=None):
            b = alumno.fnac
            next_bd = b.replace(year=hoy.year)
            if next_bd < hoy:
                next_bd = next_bd.replace(year=hoy.year + 1)
            diff = (next_bd - hoy).days
            if diff <= dias:
                resultado.append({"id": alumno.id, "nombre": alumno.nombre, "fnac": alumno.fnac, "dias": diff})
        return Response(sorted(resultado, key=lambda x: x["dias"]))

    @action(detail=True, methods=["post"], url_path="asignar-grupo")
    def asignar_grupo(self, request, pk=None):
        alumno = self.get_object()
        AlumnoGrupo.objects.update_or_create(
            alumno=alumno, grupo_id=request.data.get("grupo_id"),
            defaults={"horarios": request.data.get("horarios", [])},
        )
        return Response({"ok": True})
