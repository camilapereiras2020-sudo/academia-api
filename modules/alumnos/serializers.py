
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
    marca_display = serializers.CharField(source="get_marca_display", read_only=True)

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
            "id", "nombre", "marca", "marca_display", "fecha_nacimiento", "fnac", "telefono", "email", "dni",
            "aviso_cumple_dias", "grupo", "grupo_nombre",
            "grupos_detalle", "pagador", "pagador_nombre", "empresa", "empresa_nombre",
            "es_fundae", "nivel", "notas", "activo", "created_at",
        ]
        read_only_fields = ["id", "created_at", "grupos_detalle"]


class AlumnoReceptionSerializer(AlumnoSerializer):
    """Restricted view for role="reception": basic contact info, read+write,
    plus read-only marca/grupo context so she knows who's in which class.
    Everything financial/administrative (pagador, empresa, notas, nivel,
    es_fundae, activo, fecha_nacimiento) is intentionally left out."""

    class Meta(AlumnoSerializer.Meta):
        fields = ["id", "nombre", "telefono", "email", "marca", "marca_display", "grupo", "grupo_nombre", "grupos_detalle"]
        read_only_fields = ["id", "marca", "marca_display", "grupo", "grupo_nombre", "grupos_detalle"]
