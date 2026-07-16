from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ROLE_CHOICES

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=ROLE_CHOICES, required=False, default="owner")

    class Meta:
        model = User
        fields = ["email", "username", "password", "password2", "academia_nombre", "role"]

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError("Las contrasenas no coinciden.")
        return data

    def create(self, validated_data):
        validated_data.pop("password2")
        return User.objects.create_user(**validated_data)

class UserProfileSerializer(serializers.ModelSerializer):
    # academia_* fields describe the business (the tenant), not the individual
    # staff account — for a delegated account (co_manager/reception) these must
    # read/write the owner's row, not the logged-in user's own (blank) one.
    ACADEMIA_FIELDS = ["academia_nombre", "academia_nif", "academia_dir", "academia_tel", "academia_logo"]

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "role", "marca_asignada",
            "academia_nombre", "academia_nif", "academia_dir", "academia_tel", "academia_logo",
        ]
        read_only_fields = ["id", "email", "role", "marca_asignada"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        tenant = instance.tenant
        if tenant != instance:
            for field in self.ACADEMIA_FIELDS:
                data[field] = getattr(tenant, field)
        return data

    def update(self, instance, validated_data):
        academia_data = {f: validated_data.pop(f) for f in self.ACADEMIA_FIELDS if f in validated_data}
        if academia_data:
            tenant = instance.tenant
            for field, value in academia_data.items():
                setattr(tenant, field, value)
            tenant.save(update_fields=list(academia_data))
        return super().update(instance, validated_data)
