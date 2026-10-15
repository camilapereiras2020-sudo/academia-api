from rest_framework import serializers
from modules.core.mixins import TenantScopedFKMixin
from modules.alumnos.models import Alumno
from .models import Tarifa, CargoExtra


class TarifaSerializer(serializers.ModelSerializer):
    nombre_display = serializers.CharField(source="get_nombre_display", read_only=True)
    tipo_cobro_display = serializers.CharField(source="get_tipo_cobro_display", read_only=True)
    marca_display = serializers.CharField(source="get_marca_display", read_only=True)

    class Meta:
        model = Tarifa
        fields = [
            "id", "nombre", "nombre_display", "tipo_cobro", "tipo_cobro_display",
            "marca", "marca_display", "precio", "horas_semanales", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CargoExtraSerializer(TenantScopedFKMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"alumno": Alumno}

    class Meta:
        model = CargoExtra
        fields = ["id", "alumno", "concepto", "monto", "fecha", "created_at"]
        read_only_fields = ["id", "created_at"]
