from rest_framework import serializers
from .models import Pago
from modules.tarifas.models import MARCA_CHOICES, Tarifa
from modules.core.mixins import TenantScopedFKMixin
from modules.alumnos.models import Alumno
from modules.pagadores.models import Pagador
from modules.grupos.models import Grupo

class PagoSerializer(TenantScopedFKMixin, serializers.ModelSerializer):
    tenant_scoped_fields = {"alumno": Alumno, "pagador": Pagador, "grupo": Grupo, "tarifa": Tarifa}

    # Required on create despite the model's default="rangers_academy" —
    # that default exists only so internal scripts (healthcheck.py etc.)
    # don't need to care about it; a real Pago must have an explicit,
    # deliberate brand choice. PATCH stays exempt (DRF skips required-field
    # checks for partial updates), so completing a draft that already has
    # a marca doesn't force resending it.
    marca = serializers.ChoiceField(choices=MARCA_CHOICES, required=True)
    pagador_nombre = serializers.CharField(source="pagador.nombre", read_only=True, default=None)
    alumno_nombre  = serializers.CharField(source="alumno.nombre",  read_only=True, default=None)
    grupo_nombre   = serializers.CharField(source="grupo.nombre",   read_only=True, default=None)
    emisor_nombre  = serializers.CharField(source="emisor.nombre",  read_only=True, default=None)
    tarifa_nombre  = serializers.CharField(source="tarifa.get_nombre_display", read_only=True, default=None)
    marca_display  = serializers.CharField(source="get_marca_display", read_only=True)

    class Meta:
        model  = Pago
        fields = [
            "id", "marca", "marca_display", "pagador", "pagador_nombre", "alumno", "alumno_nombre",
            "grupo", "grupo_nombre", "emisor", "emisor_nombre",
            "tarifa", "tarifa_nombre",
            "periodo", "mensualidad", "descuento", "extras", "total",
            "metodo", "estado", "fecha", "horas_trabajadas", "notas",
            "num_doc", "serie_id", "iban", "stripe_payment_intent", "created_at",
            "estado_carga", "numero_factura_reservado", "concepto_original", "concepto_libre",
        ]
        read_only_fields = [
            "id", "created_at", "num_doc", "serie_id", "emisor", "emisor_nombre", "tarifa_nombre",
            "estado_carga", "numero_factura_reservado", "concepto_original",
        ]

    def validate(self, attrs):
        instance = self.instance
        if instance and instance.pk:
            alumno_after  = attrs.get("alumno", instance.alumno)
            pagador_after = attrs.get("pagador", instance.pagador)
            if (alumno_after is None or pagador_after is None) and \
                    instance.documentos.exclude(estado="borrador").exists():
                raise serializers.ValidationError(
                    "No se puede quitar alumno/pagador de un pago con documentos ya emitidos."
                )
        return attrs
