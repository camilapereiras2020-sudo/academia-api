from rest_framework import serializers
from .models import Grupo

class GrupoSerializer(serializers.ModelSerializer):
    alumnos_count = serializers.SerializerMethodField()

    class Meta:
        model = Grupo
        fields = ["id", "nombre", "nivel", "tarifa", "aula", "color_idx", "horarios", "alumnos_count", "created_at"]
        read_only_fields = ["id", "created_at", "alumnos_count"]

    def get_alumnos_count(self, obj):
        return obj.alumno_set.count()
