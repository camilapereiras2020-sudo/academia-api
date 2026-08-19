
from rest_framework import serializers
from .models import Grupo


class GrupoSerializer(serializers.ModelSerializer):
    alumnos_count = serializers.SerializerMethodField()
    tipo_cobro_display = serializers.CharField(source="get_tipo_cobro_display", read_only=True)
    marca_display = serializers.CharField(source="get_marca_display", read_only=True)

    class Meta:
        model = Grupo
        fields = [
            "id", "nombre", "marca", "marca_display", "nivel", "profesor", "tipo_cobro", "tipo_cobro_display",
            "tarifa", "precio_hora", "aula", "color_idx", "horarios",
            "alumnos_count", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_alumnos_count(self, obj):
        return obj.alumnos.count()
