import logging

from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.db.models import Count, Q
from django.utils import timezone
from modules.authentication.rbac import NotReception, marca_scope_for
from .models import Lead, Interaccion
from .serializers import LeadSerializer, LeadListSerializer, InteraccionSerializer
from .sheets_service import append_contacto_row

logger = logging.getLogger(__name__)


class LeadViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, NotReception]

    def get_serializer_class(self):
        if self.action == "list":
            return LeadListSerializer
        return LeadSerializer

    def get_queryset(self):
        qs = Lead.objects.filter(academia=self.request.user.tenant)
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(marca=scope)
        etapa = self.request.query_params.get("etapa")
        if etapa:
            qs = qs.filter(etapa=etapa)
        return qs

    def perform_create(self, serializer):
        scope = marca_scope_for(self.request.user)
        if scope:
            provided = serializer.validated_data.get("marca")
            if provided and provided != scope:
                raise PermissionDenied(f"Solo podés crear leads de la marca {scope}.")
            lead = serializer.save(academia=self.request.user.tenant, marca=scope)
        else:
            lead = serializer.save(academia=self.request.user.tenant)
        try:
            append_contacto_row(lead)
        except Exception:
            logger.exception("Failed to append lead %s to Contactos sheet", lead.id)

    def perform_update(self, serializer):
        scope = marca_scope_for(self.request.user)
        if scope:
            provided = serializer.validated_data.get("marca")
            if provided and provided != scope:
                raise PermissionDenied(f"Solo podés editar leads de la marca {scope}.")
            serializer.save(marca=scope)
        else:
            serializer.save()

    @action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        qs = Lead.objects.filter(academia=request.user.tenant)
        scope = marca_scope_for(request.user)
        if scope:
            qs = qs.filter(marca=scope)
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

    @action(detail=False, methods=["get"], url_path="recordatorios")
    def recordatorios(self, request):
        """Leads that need a follow-up decision right now: either a
        proximo_seguimiento date that has passed, or no logged contact in
        a while. Backs the login popup — kept separate from `dashboard`
        (which still drives the reception summary tiles) so each can
        evolve independently.

        Two reasons, not mutually exclusive per lead:
        - vencido: proximo_seguimiento was set and it's in the past.
        - sin_contacto: dias_sin_contacto > 5 (same threshold as the red
          badge in CRMPage), regardless of whether a seguimiento date was
          ever set.
        """
        qs = Lead.objects.filter(academia=request.user.tenant).exclude(
            etapa__in=["matriculado", "archivado", "frio"]
        )
        scope = marca_scope_for(request.user)
        if scope:
            qs = qs.filter(marca=scope)

        leads = []
        for lead in qs:
            vencido = lead.seguimiento_vencido
            sin_contacto = lead.dias_sin_contacto > 5
            if not (vencido or sin_contacto):
                continue
            data = LeadListSerializer(lead).data
            data["razon"] = "vencido" if vencido else "sin_contacto"
            leads.append((lead.proximo_seguimiento or lead.created_at.date(), data))

        leads.sort(key=lambda pair: pair[0])
        return Response({
            "count": len(leads),
            "leads": [d for _, d in leads],
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
        from decimal import Decimal, InvalidOperation

        from modules.alumnos.models import Alumno
        from modules.pagadores.services import get_or_create_pagador
        from modules.grupos.models import Grupo
        from modules.pagos.models import Pago

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

        try:
            mensualidad_decimal = Decimal(str(mensualidad))
        except (InvalidOperation, ValueError, TypeError):
            return Response(
                {"error": "mensualidad inválida"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # grupo_id comes straight from the request — without this, a lead
        # could get matriculated into another tenant's group, or a group of
        # the wrong marca for this lead.
        try:
            grupo = Grupo.objects.get(id=grupo_id, academia=request.user.tenant, marca=lead.marca)
        except Grupo.DoesNotExist:
            return Response(
                {"error": "Grupo no encontrado para esta marca."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Adult self-pay: auto-create/dedup the Pagador from the alumno's own
        # data, same as the self-pay path in AlumnoViewSet. For a minor lead,
        # do NOT guess a payer from lead.nombre_contacto — leave Alumno.pagador
        # unset and let the front desk fill it in via the unified alumno form
        # right after matriculation (matriculation already navigates to the
        # alumno profile, so this is a clean, non-lossy handoff).
        pagador = None
        if lead.es_adulto and lead.pagador_es_alumno:
            pagador = get_or_create_pagador(
                academia=request.user.tenant,
                nombre=lead.nombre_alumno,
                telefono=lead.telefono,
                email=lead.email,
            )

        alumno = Alumno.objects.create(
            academia=request.user.tenant,
            nombre=lead.nombre_alumno,
            marca=lead.marca,
            pagador=pagador,
            grupo=grupo,
            nivel=lead.nivel_estimado or "",
            notas=lead.notas or "",
            es_adulto=lead.es_adulto,
        )

        pago = Pago.objects.create(
            academia=request.user.tenant,
            marca=lead.marca,
            pagador=pagador,
            alumno=alumno,
            grupo=grupo,
            periodo=fecha_inicio[:7],
            mensualidad=mensualidad_decimal,
            total=mensualidad_decimal,
            metodo="",
            estado="pendiente",
            fecha=fecha_inicio,
            estado_carga="pendiente_completar",
            notas="Primer pago generado automáticamente al matricular.",
        )

        lead.alumno = alumno
        lead.etapa = "matriculado"
        lead.save(update_fields=["alumno", "etapa", "updated_at"])

        return Response({
            "lead": LeadSerializer(lead).data,
            "alumno_id": alumno.id,
            "alumno_nombre": alumno.nombre,
            "pagador_id": pagador.id if pagador else None,
            "pagador_nombre": pagador.nombre if pagador else None,
            "pagador_autocompletado": lead.es_adulto and lead.pagador_es_alumno,
            "pago_id": pago.id,
        })


class InteraccionViewSet(ModelViewSet):
    serializer_class = InteraccionSerializer
    permission_classes = [permissions.IsAuthenticated, NotReception]

    def get_queryset(self):
        qs = Interaccion.objects.filter(lead__academia=self.request.user.tenant)
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(lead__marca=scope)
        return qs

    def perform_create(self, serializer):
        # Logging an interaction is the one event that should actually reset
        # the "went cold" clock — unlike Lead.updated_at (an auto_now field
        # that changes on any unrelated edit), last_contacted_at only moves
        # when someone genuinely logs a contact here.
        interaccion = serializer.save()
        interaccion.lead.last_contacted_at = interaccion.fecha
        interaccion.lead.save(update_fields=["last_contacted_at"])
