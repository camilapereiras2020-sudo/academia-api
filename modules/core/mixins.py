from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response


class ContactableViaPagadorMixin:
    """Adds enviar-email/whatsapp-link actions to a ViewSet whose objects
    have — or *are* — a Pagador to contact. Was duplicated verbatim between
    AlumnoViewSet and PagadorViewSet before this existed.

    Set `pagador_attr` to the attribute name holding the Pagador (e.g.
    "pagador" for AlumnoViewSet), or leave it "" if the viewset's own
    object IS the Pagador (PagadorViewSet).
    """

    pagador_attr = ""

    def _get_pagador(self, obj):
        return getattr(obj, self.pagador_attr) if self.pagador_attr else obj

    @action(detail=True, methods=["post"], url_path="enviar-email")
    def enviar_email(self, request, pk=None):
        from modules.core.email_service import send_email
        pagador = self._get_pagador(self.get_object())
        if not pagador or not pagador.email:
            return Response(
                {"error": "No se encontró un pagador con email registrado."},
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
            return Response({"ok": True, "id": msg_id, "enviado_a": pagador.email})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=["get"], url_path="whatsapp-link")
    def whatsapp_link(self, request, pk=None):
        from modules.core.whatsapp_service import whatsapp_link as build_whatsapp_link
        pagador = self._get_pagador(self.get_object())
        if not pagador or not pagador.telefono:
            return Response(
                {"error": "No se encontró un pagador con teléfono registrado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        texto = request.query_params.get("texto", "")
        return Response({"url": build_whatsapp_link(pagador.telefono, texto), "enviado_a": pagador.telefono})


class TenantScopedFKMixin:
    """Constrains this serializer's writable FK fields to the requesting
    user's tenant — and, for models that have a `marca` column, to their
    marca scope too — so a delegated account can't attach a record to
    another tenant's or brand's alumno/pagador/grupo/etc. just by knowing
    (or guessing) its id. Without this, DRF's PrimaryKeyRelatedField
    defaults to `Model.objects.all()`, so `get_queryset()`/`marca_scope_for`
    checks on the *primary* object never protect its FK targets.

    Usage:
        class FooSerializer(TenantScopedFKMixin, serializers.ModelSerializer):
            tenant_scoped_fields = {"alumno": Alumno, "grupo": Grupo}
            ...

    Field name -> model. Only fields present on the serializer are touched,
    so this is safe to declare even on serializers where a field is
    sometimes read-only (e.g. a reception-restricted variant).
    """

    tenant_scoped_fields: dict = {}

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request is None or not getattr(request, "user", None) or not request.user.is_authenticated:
            return fields

        from modules.authentication.rbac import marca_scope_for
        tenant = request.user.tenant
        scope = marca_scope_for(request.user)

        for field_name, model in self.tenant_scoped_fields.items():
            field = fields.get(field_name)
            if field is None or not hasattr(field, "queryset") or field.queryset is None:
                continue
            qs = model.objects.filter(academia=tenant)
            if scope and hasattr(model, "marca"):
                qs = qs.filter(marca=scope)
            field.queryset = qs

        return fields
