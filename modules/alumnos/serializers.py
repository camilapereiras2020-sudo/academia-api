
from rest_framework import serializers
from .models import Alumno


class AlumnoSerializer(serializers.ModelSerializer):
    pagador_nombre = serializers.CharField(source="pagador.nombre", read_only=True, default="")
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True, default="")
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True, default="")
    # fnac is the frontend alias for fecha_nacimiento
    fnac = serializers.DateField(source="fecha_nacimiento", required=False, allow_null=True)
    # grupos_detalle wraps the single grupo FK in the array shape the frontend expects
    grupos_detalle = serializers.SerializerMethodField()

    def get_grupos_detalle(self, obj):
        if not obj.grupo_id:
            return []
        return [{
            "grupo": obj.grupo_id,
            "grupo_nombre": obj.grupo.nombre if obj.grupo else "",
            "horarios": [],
        }]

    class Meta:
        model = Alumno
        fields = [
            "id", "nombre", "fecha_nacimiento", "fnac", "telefono", "email", "dni",
            "aviso_cumple_dias", "grupo", "grupo_nombre",
            "grupos_detalle", "pagador", "pagador_nombre", "empresa", "empresa_nombre",
            "es_fundae", "nivel", "notas", "activo", "created_at",
        ]
        read_only_fields = ["id", "created_at", "grupos_detalle"]
