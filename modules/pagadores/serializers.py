from rest_framework import serializers
from .models import Pagador

class PagadorSerializer(serializers.ModelSerializer):
    alumnos_count = serializers.IntegerField(source="alumnos.count", read_only=True)

    class Meta:
        model = Pagador
        fields = ["id", "nombre", "nif", "telefono", "email", "direccion", "metodo", "frecuencia", "iban", "notas", "fnac", "aviso_cumple_dias", "alumnos_count", "created_at"]
        read_only_fields = ["id", "created_at", "alumnos_count"]
