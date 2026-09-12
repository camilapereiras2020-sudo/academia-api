from rest_framework import serializers
from .models import Pagador

class PagadorSerializer(serializers.ModelSerializer):
    alumnos_count = serializers.IntegerField(source="alumnos.count", read_only=True)
    es_alumno_adulto = serializers.SerializerMethodField()

    class Meta:
        model = Pagador
        fields = ["id", "nombre", "nif", "telefono", "email", "direccion", "metodo", "frecuencia", "iban", "notas", "fnac", "aviso_cumple_dias", "alumnos_count", "es_alumno_adulto", "created_at"]
        read_only_fields = ["id", "created_at", "alumnos_count", "es_alumno_adulto"]

    def get_es_alumno_adulto(self, obj):
        # True only for the "self-pay adult" case: this Pagador is really
        # just the one adult alumno paying for themselves, not a parent/
        # guardian — the alumnos list ("hijos") is misleading in that case.
        alumnos = list(obj.alumnos.all())
        return len(alumnos) == 1 and alumnos[0].es_adulto
