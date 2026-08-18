from rest_framework import serializers
from .models import Nivel


class NivelSerializer(serializers.ModelSerializer):
    categoria_display = serializers.CharField(source="get_categoria_display", read_only=True)

    class Meta:
        model = Nivel
        fields = ["id", "nombre", "categoria", "categoria_display", "orden", "activo", "created_at"]
        read_only_fields = ["id", "created_at"]
