
from rest_framework import serializers
from .models import Empresa, ContactoEmpresa

class ContactoEmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactoEmpresa
        fields = ["id", "empresa", "nombre", "cargo", "email", "telefono", "notas", "created_at"]
        read_only_fields = ["id", "created_at"]

class EmpresaSerializer(serializers.ModelSerializer):
    contactos = ContactoEmpresaSerializer(many=True, read_only=True)
    num_alumnos = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = ["id", "nombre", "cif", "email", "telefono", "direccion",
                  "facturacion", "notas", "activa", "contactos", "num_alumnos", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_num_alumnos(self, obj):
        return obj.alumnos.count()

class EmpresaListSerializer(serializers.ModelSerializer):
    num_alumnos = serializers.SerializerMethodField()
    num_contactos = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = ["id", "nombre", "cif", "email", "telefono", "facturacion",
                  "activa", "num_alumnos", "num_contactos", "created_at"]

    def get_num_alumnos(self, obj):
        return obj.alumnos.count()

    def get_num_contactos(self, obj):
        return obj.contactos.count()
