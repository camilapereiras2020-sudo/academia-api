from rest_framework import serializers
from .models import Lead, Interaccion


class InteraccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interaccion
        fields = ["id", "lead", "tipo", "fecha", "resumen", "proxima_accion"]
        read_only_fields = ["id", "fecha"]


class LeadSerializer(serializers.ModelSerializer):
    interacciones = InteraccionSerializer(many=True, read_only=True)
    horas_sin_mover = serializers.ReadOnlyField()
    etapa_display = serializers.CharField(source="get_etapa_display", read_only=True)
    origen_display = serializers.CharField(source="get_origen_display", read_only=True)
    objetivo_display = serializers.CharField(source="get_objetivo_display", read_only=True)
    marca_display = serializers.CharField(source="get_marca_display", read_only=True)
    alerta = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id", "marca", "marca_display", "nombre_contacto", "nombre_alumno", "edad_alumno",
            "curso_escolar", "telefono", "email", "objetivo", "objetivo_display",
            "es_adulto", "pagador_es_alumno",
            "nivel_estimado", "disponibilidad", "colegio", "necesidades_especiales",
            "origen", "origen_display", "notas", "etapa", "etapa_display",
            "proximo_seguimiento", "alumno", "horas_sin_mover", "alerta",
            "interacciones", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "telefono": {"required": False, "allow_blank": True},
            "objetivo": {"required": False},
            "nombre_contacto": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        es_adulto = attrs.get("es_adulto", getattr(self.instance, "es_adulto", False))
        nombre_contacto = attrs.get("nombre_contacto", getattr(self.instance, "nombre_contacto", ""))
        if not es_adulto and not nombre_contacto.strip():
            raise serializers.ValidationError(
                {"nombre_contacto": "Este campo es obligatorio salvo que el alumno sea adulto."}
            )
        return attrs

    def get_alerta(self, obj):
        return obj.horas_sin_mover > 24


class LeadListSerializer(serializers.ModelSerializer):
    etapa_display = serializers.CharField(source="get_etapa_display", read_only=True)
    origen_display = serializers.CharField(source="get_origen_display", read_only=True)
    marca_display = serializers.CharField(source="get_marca_display", read_only=True)
    alerta = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id", "marca", "marca_display", "nombre_contacto", "nombre_alumno", "edad_alumno",
            "telefono", "objetivo", "es_adulto", "alumno", "etapa", "etapa_display",
            "origen_display", "alerta", "proximo_seguimiento",
            "created_at", "updated_at",
        ]

    def get_alerta(self, obj):
        return obj.horas_sin_mover > 24
