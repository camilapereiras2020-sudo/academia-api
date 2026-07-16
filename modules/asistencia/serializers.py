from rest_framework import serializers
from .models import Sesion, RegistroAsistencia
from modules.core.mixins import TenantScopedFKMixin
from modules.grupos.models import Grupo
from modules.alumnos.models import Alumno

class RegistroSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.CharField(source="alumno.nombre", read_only=True)

    class Meta:
        model = RegistroAsistencia
        fields = ["id", "alumno", "alumno_nombre", "estado", "nota", "es_invitado"]

class SesionSerializer(TenantScopedFKMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"grupo": Grupo}
    registros = RegistroSerializer(many=True, read_only=True)
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)

    class Meta:
        model = Sesion
        fields = ["id", "grupo", "grupo_nombre", "fecha", "hora", "notas", "contenido", "registros", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        registros_data = self.context["request"].data.get("registros", [])
        tenant = self.context["request"].user.tenant

        # registros bypasses validated_data (raw request data, not a nested
        # serializer) — same gap as TareaSerializer.completados, needs its
        # own tenant check since the mixin only covers the `grupo` field.
        alumno_ids = {r["alumno"] for r in registros_data if "alumno" in r}
        valid_ids = set(
            Alumno.objects.filter(academia=tenant, id__in=alumno_ids).values_list("id", flat=True)
        )
        invalid_ids = alumno_ids - valid_ids
        if invalid_ids:
            raise serializers.ValidationError(
                {"registros": f"Alumno(s) no encontrados: {sorted(invalid_ids)}"}
            )

        sesion = Sesion.objects.create(**validated_data)
        for r in registros_data:
            RegistroAsistencia.objects.create(sesion=sesion, **r)
        return sesion
