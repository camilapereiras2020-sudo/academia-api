from rest_framework import serializers
from .models import Profesor


class ProfesorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profesor
        fields = ["id", "nombre", "codigo", "es_suplente", "orden", "activo", "created_at"]
        read_only_fields = ["id", "created_at"]

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
