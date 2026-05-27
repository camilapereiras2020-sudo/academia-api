
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="Empresa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("nombre", models.CharField(max_length=200)),
                ("cif", models.CharField(max_length=20, blank=True)),
                ("email", models.EmailField(blank=True)),
                ("telefono", models.CharField(max_length=20, blank=True)),
                ("direccion", models.TextField(blank=True)),
                ("facturacion", models.CharField(max_length=20, default="global", blank=True)),
                ("notas", models.TextField(blank=True)),
                ("activa", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("academia", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="empresas", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["nombre"]},
        ),
        migrations.CreateModel(
            name="ContactoEmpresa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("nombre", models.CharField(max_length=200, blank=True)),
                ("cargo", models.CharField(max_length=100, blank=True)),
                ("email", models.EmailField(blank=True)),
                ("telefono", models.CharField(max_length=20, blank=True)),
                ("notas", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("empresa", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contactos", to="empresas.empresa")),
            ],
            options={"ordering": ["nombre"]},
        ),
    ]
