from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "username", "password", "password2", "academia_nombre"]

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError("Las contrasenas no coinciden.")
        return data

    def create(self, validated_data):
        validated_data.pop("password2")
        return User.objects.create_user(**validated_data)

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "academia_nombre", "academia_nif", "academia_dir", "academia_tel", "academia_logo"]
        read_only_fields = ["id", "email"]
