from rest_framework import serializers
from .models import Pago

class PagoSerializer(serializers.ModelSerializer):
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
