from rest_framework import serializers
from .models import Profesor


class ProfesorSerializer(serializers.ModelSerializer):
    # Cuántas clases tiene a cargo y cuántos alumnos activos están
    # matriculados en al menos una de ellas (Grupo no tiene un concepto de
    # "activo" propio; un alumno con clases con dos profesores distintos
    # suma en ambos).
    grupos_count = serializers.SerializerMethodField()
    alumnos_count = serializers.SerializerMethodField()

    class Meta:
        model = Profesor
        fields = [
            "id", "nombre", "codigo", "es_suplente", "orden", "activo", "created_at",
            "grupos_count", "alumnos_count",
        ]
        read_only_fields = ["id", "created_at", "grupos_count", "alumnos_count"]

    def get_grupos_count(self, obj):
        return obj.grupos.count()

    def get_alumnos_count(self, obj):
        from modules.alumnos.models import Alumno
        return Alumno.objects.filter(grupos__profesor=obj, activo=True).distinct().count()

    def validate_nombre(self, value):
        request = self.context.get("request")
        if request is None:
            return value
        qs = Profesor.objects.filter(academia=request.user.tenant, nombre=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un profesor con ese nombre.")
        return value
