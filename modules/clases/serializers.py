from django.db import transaction
from rest_framework import serializers
from .models import Tarea, TareaCompletada, NotaDificultad
from modules.core.mixins import TenantScopedFKMixin
from modules.grupos.models import Grupo
from modules.alumnos.models import Alumno


class TareaCompletadaSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.CharField(source="alumno.nombre", read_only=True)

    class Meta:
        model = TareaCompletada
        fields = ["id", "alumno", "alumno_nombre", "estado", "nota"]


class TareaSerializer(TenantScopedFKMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"grupo": Grupo}
    completados = TareaCompletadaSerializer(many=True, read_only=True)
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)

    class Meta:
        model = Tarea
        fields = [
            "id", "grupo", "grupo_nombre", "sesion", "titulo", "descripcion",
            "fecha_asignada", "fecha_entrega", "completados", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        completados_data = self.context["request"].data.get("completados", [])
        tenant = self.context["request"].user.tenant
        seen_alumnos = set()
        for c in completados_data:
            if c["alumno"] in seen_alumnos:
                raise serializers.ValidationError(
                    {"completados": f"El alumno {c['alumno']} aparece más de una vez."}
                )
            seen_alumnos.add(c["alumno"])

        # completados bypasses validated_data (it's built from raw request
        # data, not a nested serializer), so it needs its own tenant check —
        # the tenant_scoped_fields mixin only covers the `grupo` field above.
        valid_ids = set(
            Alumno.objects.filter(academia=tenant, id__in=seen_alumnos).values_list("id", flat=True)
        )
        invalid_ids = seen_alumnos - valid_ids
        if invalid_ids:
            raise serializers.ValidationError(
                {"completados": f"Alumno(s) no encontrados: {sorted(invalid_ids)}"}
            )

        with transaction.atomic():
            tarea = Tarea.objects.create(**validated_data)
            for c in completados_data:
                TareaCompletada.objects.create(
                    tarea=tarea,
                    alumno_id=c["alumno"],
                    estado=c.get("estado", "pendiente"),
                    nota=c.get("nota", ""),
                )
        return tarea


class NotaDificultadSerializer(TenantScopedFKMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"grupo": Grupo, "alumno": Alumno}
    alumno_nombre = serializers.CharField(source="alumno.nombre", read_only=True)
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)

    class Meta:
        model = NotaDificultad
        fields = [
            "id", "grupo", "grupo_nombre", "alumno", "alumno_nombre",
            "tema", "nota", "fecha", "sesion", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
