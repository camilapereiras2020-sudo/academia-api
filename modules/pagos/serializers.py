from rest_framework import serializers
from .models import Pago

class PagoSerializer(serializers.ModelSerializer):
    pagador_nombre = serializers.CharField(source="pagador.nombre", read_only=True)
    alumno_nombre = serializers.CharField(source="alumno.nombre", read_only=True)
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)

    class Meta:
        model = Pago
        fields = ["id", "pagador", "pagador_nombre", "alumno", "alumno_nombre", "grupo", "grupo_nombre", "periodo", "mensualidad", "descuento", "extras", "total", "metodo", "estado", "fecha", "notas", "num_doc", "serie_id", "iban", "stripe_payment_intent", "created_at"]
        read_only_fields = ["id", "created_at", "num_doc"]
