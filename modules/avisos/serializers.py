from rest_framework import serializers
from .models import Aviso, AvisoMensaje


class AvisoSerializer(serializers.ModelSerializer):
    creado_por_nombre = serializers.CharField(source="creado_por.username", read_only=True)
    para_nombre = serializers.CharField(source="para.username", read_only=True)
    # Anotados por AvisoViewSet.get_queryset (evita una consulta por aviso).
    mensajes_count = serializers.IntegerField(read_only=True, default=0)
    ultimo_texto = serializers.CharField(read_only=True, default="")
    no_leido = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Aviso
        fields = [
            "id", "titulo", "fecha", "hecha", "para", "para_nombre", "para_todos",
            "creado_por", "creado_por_nombre", "created_at",
            "ultima_actividad", "mensajes_count", "ultimo_texto", "no_leido",
        ]
        read_only_fields = [
            "id", "creado_por", "creado_por_nombre", "para_nombre", "created_at",
            "ultima_actividad", "mensajes_count", "ultimo_texto", "no_leido",
        ]

    def validate_para(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        tenant = request.user.tenant
        if value.id != tenant.id and value.academia_owner_id != tenant.id:
            raise serializers.ValidationError("Esa persona no pertenece a tu academia.")
        return value

    def validate(self, attrs):
        # Un aviso es para una persona o para todo el equipo, nunca las dos cosas.
        if attrs.get("para_todos"):
            attrs["para"] = None
        elif attrs.get("para") is not None and self.instance is not None:
            attrs["para_todos"] = False
        return attrs


class AvisoMensajeSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.CharField(source="autor.username", read_only=True)

    class Meta:
        model = AvisoMensaje
        fields = ["id", "aviso", "autor", "autor_nombre", "texto", "created_at"]
        read_only_fields = ["id", "aviso", "autor", "autor_nombre", "created_at"]

    def validate_texto(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("El mensaje no puede estar vacío.")
        return value
