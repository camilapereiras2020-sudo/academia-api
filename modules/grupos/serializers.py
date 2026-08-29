
from rest_framework import serializers
from .models import Grupo, Aula
from modules.profesores.models import Profesor


class AulaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aula
        fields = ["id", "nombre", "codigo", "activo", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_nombre(self, value):
        request = self.context.get("request")
        if request is None:
            return value
        qs = Aula.objects.filter(academia=request.user.tenant, nombre=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un aula con ese nombre.")
        return value


class GrupoSerializer(serializers.ModelSerializer):
    alumnos_count = serializers.SerializerMethodField()
    tipo_cobro_display = serializers.CharField(source="get_tipo_cobro_display", read_only=True)
    marca_display = serializers.CharField(source="get_marca_display", read_only=True)
    profesor_nombre = serializers.CharField(source="profesor.nombre", read_only=True, default=None)

    class Meta:
        model = Grupo
        fields = [
            "id", "nombre", "marca", "marca_display", "nivel", "profesor", "profesor_nombre",
            "tipo_cobro", "tipo_cobro_display",
            "tarifa", "precio_hora", "aula", "color_idx", "horarios",
            "alumnos_count", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_alumnos_count(self, obj):
        return obj.alumnos.count()

    def validate_profesor(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request and value.academia_id != request.user.tenant.id:
            raise serializers.ValidationError("Profesor no pertenece a esta academia.")
        return value
