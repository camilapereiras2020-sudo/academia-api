from rest_framework import serializers
from .models import Alumno, AlumnoGrupo

class AlumnoGrupoSerializer(serializers.ModelSerializer):
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)

    class Meta:
        model = AlumnoGrupo
        fields = ["grupo", "grupo_nombre", "horarios"]

class AlumnoSerializer(serializers.ModelSerializer):
    grupos_detalle = AlumnoGrupoSerializer(source="alumnogrupo_set", many=True, read_only=True)

    class Meta:
        model = Alumno
        fields = ["id", "nombre", "fnac", "telefono", "email", "notas", "aviso_cumple_dias", "pagador", "grupos_detalle", "created_at"]
        read_only_fields = ["id", "created_at"]
