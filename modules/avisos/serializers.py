from rest_framework import serializers
from .models import Aviso


class AvisoSerializer(serializers.ModelSerializer):
    creado_por_nombre = serializers.CharField(source="creado_por.username", read_only=True)
    para_nombre = serializers.CharField(source="para.username", read_only=True)

    class Meta:
        model = Aviso
        fields = [
            "id", "titulo", "fecha", "hecha", "para", "para_nombre",
            "creado_por", "creado_por_nombre", "created_at",
        ]
        read_only_fields = ["id", "creado_por", "creado_por_nombre", "para_nombre", "created_at"]

    def validate_para(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        tenant = request.user.tenant
        if value.id != tenant.id and value.academia_owner_id != tenant.id:
            raise serializers.ValidationError("Esa persona no pertenece a tu academia.")
        return value
