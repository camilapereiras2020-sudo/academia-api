
from rest_framework import serializers
from .models import Alumno


class AlumnoSerializer(serializers.ModelSerializer):
    pagador_nombre = serializers.CharField(source="pagador.nombre", read_only=True, default="")
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True, default="")
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True, default="")

    class Meta:
        model = Alumno
        fields = [
            "id", "nombre", "fecha_nacimiento", "grupo", "grupo_nombre",
            "pagador", "pagador_nombre", "empresa", "empresa_nombre",
            "es_fundae", "nivel", "notas", "activo", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
