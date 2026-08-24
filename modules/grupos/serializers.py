
from rest_framework import serializers
from .models import Grupo
from modules.profesores.models import Profesor


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
