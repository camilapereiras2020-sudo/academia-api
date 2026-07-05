from rest_framework import serializers
from .models import Documento


class DocumentoSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    pago_info = serializers.SerializerMethodField()

    class Meta:
        model = Documento
        fields = [
            "id", "pago", "tipo", "nombre", "num_doc",
            "mime_type", "download_url", "pago_info", "created_at",
            "estado", "emitida_at", "anulada_at", "motivo_anulacion",
        ]
        read_only_fields = [
            "id", "created_at", "download_url", "pago_info",
            "estado", "emitida_at", "anulada_at", "motivo_anulacion",
        ]

    def get_download_url(self, obj):
        return f"/api/v1/documentos/{obj.id}/descargar/"

    def get_pago_info(self, obj):
        if obj.pago:
            return {
                "alumno": obj.pago.alumno.nombre,
                "pagador": obj.pago.pagador.nombre,
                "periodo": obj.pago.periodo,
                "total": str(obj.pago.total),
            }
        return None
