from rest_framework import serializers
from .models import Tarea, TareaCompletada, NotaDificultad


class TareaCompletadaSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.CharField(source="alumno.nombre", read_only=True)

    class Meta:
        model = TareaCompletada
        fields = ["id", "alumno", "alumno_nombre", "estado", "nota"]


class TareaSerializer(serializers.ModelSerializer):
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
        tarea = Tarea.objects.create(**validated_data)
        for c in completados_data:
            TareaCompletada.objects.create(
                tarea=tarea,
                alumno_id=c["alumno"],
                estado=c.get("estado", "pendiente"),
                nota=c.get("nota", ""),
            )
        return tarea


class NotaDificultadSerializer(serializers.ModelSerializer):
    alumno_nombre = serializers.CharField(source="alumno.nombre", read_only=True)
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)

    class Meta:
        model = NotaDificultad
        fields = [
            "id", "grupo", "grupo_nombre", "alumno", "alumno_nombre",
            "tema", "nota", "fecha", "sesion", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
