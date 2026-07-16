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
