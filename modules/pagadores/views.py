from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import NotReception, marca_scope_for
from .models import Pagador
from .serializers import PagadorSerializer


class PagadorViewSet(ModelViewSet):
    serializer_class = PagadorSerializer
    permission_classes = [permissions.IsAuthenticated, NotReception]

    def get_queryset(self):
        qs = Pagador.objects.filter(academia=self.request.user.tenant).prefetch_related("alumnos")
        scope = marca_scope_for(self.request.user)
        if scope:
            # A pagador with at least one child in the co_manager's marca is
            # visible in full (PagadorSerializer only exposes alumnos_count,
            # not a filtered list — the count intentionally includes any
            # siblings in the other marca too).
            qs = qs.filter(alumnos__marca=scope).distinct()
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user.tenant)

    @action(detail=True, methods=["post"], url_path="enviar-email")
    def enviar_email(self, request, pk=None):
        from modules.core.email_service import send_email
        pagador = self.get_object()
        if not pagador.email:
            return Response(
                {"error": "Este pagador no tiene email registrado"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        asunto = request.data.get("asunto", "")
        cuerpo = request.data.get("cuerpo", "")
        if not asunto or not cuerpo:
            return Response(
                {"error": "asunto y cuerpo son obligatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            msg_id = send_email(
                to=pagador.email,
                subject=asunto,
                body=cuerpo,
                academia_nombre=getattr(request.user.tenant, "academia_nombre", "") or "",
            )
            return Response({"ok": True, "id": msg_id})
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    @action(detail=True, methods=["get"], url_path="whatsapp-link")
    def whatsapp_link(self, request, pk=None):
        from modules.core.whatsapp_service import whatsapp_link
        pagador = self.get_object()
        if not pagador.telefono:
            return Response(
                {"error": "Este pagador no tiene teléfono registrado"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        texto = request.query_params.get("texto", "")
        return Response({"url": whatsapp_link(pagador.telefono, texto)})
