from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.alumnos.models import Alumno
from modules.alumnos.services import alumnos_con_cumpleanos_proximos
from modules.authentication.rbac import marca_scope_for
from modules.crm.models import Lead

CUMPLEANOS_WINDOW_DIAS = 7
WHATSAPP_PENDIENTE_ETAPAS = ["nueva_consulta", "pendiente_llamar"]


class ReceptionSummaryView(APIView):
    """Aggregates the three "needs attention" cards for the reception landing
    view in one call, so the frontend doesn't have to make three separate
    requests (and so the WhatsApp count can read CRM leads server-side —
    LeadViewSet blocks the reception role entirely, but a plain count here
    exposes no lead PII)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        alumnos_qs = Alumno.objects.filter(academia=request.user.tenant)
        leads_qs = Lead.objects.filter(academia=request.user.tenant)
        scope = marca_scope_for(request.user)
        if scope:
            alumnos_qs = alumnos_qs.filter(marca=scope)
            leads_qs = leads_qs.filter(marca=scope)

        cumpleanos = alumnos_con_cumpleanos_proximos(alumnos_qs, CUMPLEANOS_WINDOW_DIAS)

        whatsapp_pendientes_count = leads_qs.filter(
            origen="whatsapp", etapa__in=WHATSAPP_PENDIENTE_ETAPAS
        ).count()

        alumnos_incompletos = list(
            alumnos_qs.filter(Q(telefono="") | Q(email=""))
            .values("id", "nombre", "telefono", "email")
        )

        return Response({
            "cumpleanos": cumpleanos,
            "whatsapp_pendientes_count": whatsapp_pendientes_count,
            "alumnos_incompletos": alumnos_incompletos,
        })
