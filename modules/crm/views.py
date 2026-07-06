import logging

from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.db.models import Count, Q
from django.utils import timezone
from .models import Lead, Interaccion
from .serializers import LeadSerializer, LeadListSerializer, InteraccionSerializer
from .sheets_service import append_contacto_row

logger = logging.getLogger(__name__)


class LeadViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "list":
            return LeadListSerializer
        return LeadSerializer

    def get_queryset(self):
        qs = Lead.objects.filter(academia=self.request.user)
        etapa = self.request.query_params.get("etapa")
        if etapa:
            qs = qs.filter(etapa=etapa)
        return qs

    def perform_create(self, serializer):
        lead = serializer.save(academia=self.request.user)
        try:
            append_contacto_row(lead)
        except Exception:
            logger.exception("Failed to append lead %s to Contactos sheet", lead.id)

    @action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        qs = Lead.objects.filter(academia=request.user)
        now = timezone.now()

        nuevos_hoy = qs.filter(
            created_at__date=now.date()
        ).count()

        sin_mover = qs.exclude(
            etapa__in=["matriculado", "archivado", "frio"]
        ).filter(
            updated_at__lt=now - timezone.timedelta(hours=24)
        ).count()

        clases_prueba = qs.filter(etapa="clase_prueba").count()

        matriculados_mes = qs.filter(
            etapa="matriculado",
            updated_at__month=now.month,
            updated_at__year=now.year,
        ).count()

        urgentes = LeadListSerializer(
            qs.exclude(etapa__in=["matriculado", "archivado", "frio"])
            .filter(updated_at__lt=now - timezone.timedelta(hours=24))
            .order_by("updated_at")[:5],
            many=True
        ).data

        return Response({
            "nuevos_hoy": nuevos_hoy,
            "sin_mover": sin_mover,
            "clases_prueba": clases_prueba,
            "matriculados_mes": matriculados_mes,
            "urgentes": urgentes,
        })

    @action(detail=True, methods=["post"], url_path="cambiar-etapa")
    def cambiar_etapa(self, request, pk=None):
        lead = self.get_object()
        nueva_etapa = request.data.get("etapa")
        if not nueva_etapa:
            return Response({"error": "etapa requerida"}, status=status.HTTP_400_BAD_REQUEST)
        lead.etapa = nueva_etapa
        lead.save(update_fields=["etapa", "updated_at"])
        return Response(LeadSerializer(lead).data)

    @action(detail=True, methods=["post"], url_path="convertir-alumno")
    def convertir_alumno(self, request, pk=None):
        from modules.alumnos.models import Alumno
        from modules.pagadores.models import Pagador

        lead = self.get_object()

        if lead.alumno_id:
            return Response(
                {"error": "Este lead ya ha sido matriculado."},
                status=status.HTTP_400_BAD_REQUEST
            )

        grupo_id = request.data.get("grupo_id")
        mensualidad = request.data.get("mensualidad")
        fecha_inicio = request.data.get("fecha_inicio")

        if not all([grupo_id, mensualidad, fecha_inicio]):
            return Response(
                {"error": "grupo_id, mensualidad y fecha_inicio son obligatorios"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if lead.es_adulto and lead.pagador_es_alumno:
            pagador_nombre = lead.nombre_alumno
        else:
            pagador_nombre = lead.nombre_contacto

        pagador, _ = Pagador.objects.get_or_create(
            academia=request.user,
            nombre=pagador_nombre,
            defaults={
                "telefono": lead.telefono,
                "email": lead.email,
            }
        )

        alumno = Alumno.objects.create(
            academia=request.user,
            nombre=lead.nombre_alumno,
            marca=lead.marca,
            pagador=pagador,
            grupo_id=grupo_id,
            nivel=lead.nivel_estimado or "",
            notas=lead.notas or "",
        )

        lead.alumno = alumno
        lead.etapa = "matriculado"
        lead.save(update_fields=["alumno", "etapa", "updated_at"])

        return Response({
            "lead": LeadSerializer(lead).data,
            "alumno_id": alumno.id,
            "alumno_nombre": alumno.nombre,
            "pagador_id": pagador.id,
            "pagador_nombre": pagador.nombre,
            "pagador_autocompletado": lead.es_adulto and lead.pagador_es_alumno,
        })


class InteraccionViewSet(ModelViewSet):
    serializer_class = InteraccionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Interaccion.objects.filter(lead__academia=self.request.user)
