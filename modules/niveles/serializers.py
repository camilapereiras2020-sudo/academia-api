from rest_framework import serializers
from .models import Nivel


class NivelSerializer(serializers.ModelSerializer):
    categoria_display = serializers.CharField(source="get_categoria_display", read_only=True)

    class Meta:
        model = Nivel
        fields = ["id", "nombre", "categoria", "categoria_display", "orden", "activo", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        # DRF only auto-generates a uniqueness validator from Meta.unique_together,
        # not from Meta.constraints (what Nivel actually uses) — check by hand so a
        # duplicate name within the same categoria returns a clean 400 instead of
        # an unhandled IntegrityError.
        categoria = attrs.get("categoria", getattr(self.instance, "categoria", None))
        nombre    = attrs.get("nombre",    getattr(self.instance, "nombre", None))
        academia  = self.context["request"].user.tenant

        qs = Nivel.objects.filter(academia=academia, categoria=categoria, nombre=nombre)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"nombre": "Ya existe un nivel con ese nombre en esta categoría."}
            )
        return attrs
