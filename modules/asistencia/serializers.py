from rest_framework import serializers
from .models import Sesion, RegistroAsistencia

class RegistroSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.CharField(source="alumno.nombre", read_only=True)

    class Meta:
        model = RegistroAsistencia
        fields = ["id", "alumno", "alumno_nombre", "estado", "nota", "es_invitado"]

class SesionSerializer(serializers.ModelSerializer):
    registros = RegistroSerializer(many=True, read_only=True)
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)

    class Meta:
        model = Sesion
        fields = ["id", "grupo", "grupo_nombre", "fecha", "hora", "notas", "registros", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        registros_data = self.context["request"].data.get("registros", [])
        sesion = Sesion.objects.create(**validated_data)
        for r in registros_data:
            RegistroAsistencia.objects.create(sesion=sesion, **r)
        return sesion
