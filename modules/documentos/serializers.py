from rest_framework import serializers
from .models import Documento, Emisor


class EmisorSerializer(serializers.ModelSerializer):
    """Legal/billing/contact data for one brand's issuing entity (Cami&Co or
    Rangers Academy) — this is what invoice_service actually reads when
    generating a factura/recibo. Numbering-critical fields (prefixes,
    baselines, atomic counters) and drive_folder_id are deliberately left
    read-only here: this is a settings form for a person, not a place to
    accidentally break invoice sequencing or AEAT numbering continuity."""

    class Meta:
        model = Emisor
        fields = [
            "id", "slug", "nombre", "autonoma", "nif", "direccion", "ciudad",
            "telefono", "email", "iban", "factura_prefix", "recibo_prefix", "activo",
        ]
        read_only_fields = ["id", "slug", "factura_prefix", "recibo_prefix", "activo"]


class DocumentoSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    drive_url = serializers.SerializerMethodField()
    pago_info = serializers.SerializerMethodField()

    class Meta:
        model = Documento
        fields = [
            "id", "pago", "tipo", "nombre", "num_doc",
            "mime_type", "download_url", "drive_url", "pago_info", "created_at",
            "estado", "emitida_at", "anulada_at", "motivo_anulacion",
        ]
        read_only_fields = [
            "id", "created_at", "download_url", "drive_url", "pago_info",
            "estado", "emitida_at", "anulada_at", "motivo_anulacion",
        ]

    def get_download_url(self, obj):
        return f"/api/v1/documentos/{obj.id}/descargar/"

    def get_drive_url(self, obj):
        # s3_key holds the Google Drive file id (misleading name — predates
        # the Drive integration). It's filled in by a best-effort background
        # upload after generation, so it can be blank for a little while (or
        # forever, if that upload failed) — None here just means "not on
        # Drive yet", not that the document doesn't exist.
        return f"https://drive.google.com/file/d/{obj.s3_key}/view" if obj.s3_key else None

    def get_pago_info(self, obj):
        if obj.pago:
            return {
                "alumno": obj.pago.alumno.nombre if obj.pago.alumno else None,
                "pagador": (
                    obj.pago.pagador.nombre if obj.pago.pagador
                    else (obj.pago.alumno.nombre if obj.pago.alumno and getattr(obj.pago.alumno, "es_adulto", False) else None)
                ),
                "periodo": obj.pago.periodo,
                "total": str(obj.pago.total),
                "fecha": obj.pago.fecha.isoformat() if obj.pago.fecha else None,
            }
        return None
