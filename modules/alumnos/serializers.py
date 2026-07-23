
from rest_framework import serializers
from .models import Alumno, FechaImportante, NotaAlumno, DatoSalud, ConsentimientoAlumno
from modules.core.mixins import TenantScopedFKMixin
from modules.grupos.models import Grupo
from modules.pagadores.models import Pagador
from modules.empresas.models import Empresa


class AlumnoSerializer(TenantScopedFKMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"grupo": Grupo, "pagador": Pagador, "empresa": Empresa}
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
            "foto_url", "nivel_objetivo", "examen_objetivo", "colegio_origen", "idioma_nativo",
            "contacto_emergencia_nombre", "contacto_emergencia_telefono",
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


class FechaImportanteSerializer(TenantScopedFKMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"alumno": Alumno}
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = FechaImportante
        fields = ["id", "alumno", "fecha", "tipo", "tipo_display", "descripcion"]
        read_only_fields = ["id", "tipo_display"]


class NotaAlumnoSerializer(TenantScopedFKMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"alumno": Alumno}
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    autor_nombre = serializers.CharField(source="autor.email", read_only=True, default="")

    class Meta:
        model = NotaAlumno
        fields = ["id", "alumno", "autor", "autor_nombre", "fecha", "contenido", "tipo", "tipo_display"]
        read_only_fields = ["id", "autor", "autor_nombre", "fecha", "tipo_display"]


class ConsentimientoAlumnoSerializer(TenantScopedFKMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"alumno": Alumno}
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = ConsentimientoAlumno
        fields = ["id", "alumno", "tipo", "tipo_display", "firmado", "fecha_firma", "documento_url"]
        read_only_fields = ["id", "tipo_display"]


class DatoSaludSerializer(serializers.ModelSerializer):
    """Deliberately excluded from AlumnoSerializer — served only via AlumnoViewSet.salud,
    which is gated to owner/co_manager (see modules.authentication.rbac.NotReception)."""

    class Meta:
        model = DatoSalud
        fields = ["id", "alumno", "alergias", "condiciones_medicas", "medicacion"]
        read_only_fields = ["id", "alumno"]
