from rest_framework import serializers
from .models import Evento


class EventoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    marca_display = serializers.CharField(source="get_marca_display", read_only=True)

    class Meta:
        model = Evento
        fields = [
            "id", "marca", "marca_display", "tipo", "tipo_display",
            "titulo", "descripcion", "fecha", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
