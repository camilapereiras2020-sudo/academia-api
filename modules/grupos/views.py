from rest_framework import permissions
from rest_framework.viewsets import ModelViewSet
from .models import Grupo, Aula
from .serializers import GrupoSerializer, AulaSerializer

class GrupoViewSet(ModelViewSet):
    # No ReadOnlyForReception here (on purpose): reception now manages
    # classes through the Horario builder same as owner/co_manager — see
    # roles.ts PAGE_ROLES["/horario"] and the 2026-09-09 decision to give her
    # full parity there, not just view access.
    #
    # No marca_scope_for() here either (also 2026-09-09, on purpose): Cami
    # confirmed Candela/Sofía should see and manage HER classes too (Cami&Co,
    # not just Rangers Academy) from Horario — "todo, como si fuera de su
    # marca". Grupo is one of the two models Horario depends on (with
    # Alumno, see modules.alumnos.views — same decision, same day), so both
    # dropped marca scoping together. Deliberately NOT touched: pagos,
    # documentos, pagadores, crm, tarifas, asistencia, clases (homework/
    # struggle tracker) — those still scope by marca_asignada same as
    # before. This was a Horario-visibility decision, not a blanket "co_manager
    # sees everything" one; don't extend the no-scope treatment to another
    # viewset without checking with Cami first.
    serializer_class = GrupoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Grupo.objects.filter(academia=self.request.user.tenant)

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user.tenant)


class AulaViewSet(ModelViewSet):
    # Same as GrupoViewSet above — reception creates aulas inline from the
    # AulaCombobox while building a class in Horario, so this needs write
    # access too, not just GET.
    serializer_class = AulaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Aula.objects.filter(academia=self.request.user.tenant)
        activo = self.request.query_params.get("activo")
        if activo is not None:
            qs = qs.filter(activo=activo.lower() == "true")
        return qs

    def perform_create(self, serializer):
        codigo = serializer.validated_data.get("codigo") or self._next_codigo()
        serializer.save(academia=self.request.user.tenant, codigo=codigo)

    def _next_codigo(self):
        # Same simple per-tenant sequence as Profesor.codigo — see that
        # viewset's _next_codigo for the tradeoff note.
        existing = Aula.objects.filter(academia=self.request.user.tenant).count()
        return f"A{existing + 1}"
