
from rest_framework import serializers
from .models import Grupo


class GrupoSerializer(serializers.ModelSerializer):
    num_alumnos = serializers.SerializerMethodField()
    tipo_cobro_display = serializers.CharField(source="get_tipo_cobro_display", read_only=True)

    class Meta:
        model = Grupo
        fields = [
            "id", "nombre", "nivel", "tipo_cobro", "tipo_cobro_display",
            "tarifa", "precio_hora", "aula", "color_idx", "horarios",
            "num_alumnos", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_num_alumnos(self, obj):
        return obj.alumnos.count()
