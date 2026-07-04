from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from modules.tarifas.models import Tarifa

User = get_user_model()

# (nombre, tipo_cobro, marca, precio, horas_semanales)
SEED_ROWS = [
    # Rangers Academy — fixed rates
    ("clase_grupo", "por_hora", "rangers_academy", 12, None),
    ("clase_grupo", "mensual", "rangers_academy", 48, 1),
    ("clase_grupo", "mensual", "rangers_academy", 90, 2),
    ("clase_grupo", "mensual", "rangers_academy", 135, 3),
    ("bono_familia", "mensual", "rangers_academy", 90, 1),
    ("bono_familia", "mensual", "rangers_academy", 175, 2),
    ("bono_familia", "mensual", "rangers_academy", 260, 3),
    # Rangers Academy — no fixed price, entered manually per payment
    ("clase_privada", "por_hora", "rangers_academy", 0, None),
    ("clase_recuperada", "por_hora", "rangers_academy", 0, None),
    # Cami & Co — same categories, no fixed prices, entered manually per payment
    ("clase_grupo", "por_hora", "cami_and_co", 0, None),
    ("bono_familia", "mensual", "cami_and_co", 0, None),
    ("clase_privada", "por_hora", "cami_and_co", 0, None),
    ("clase_recuperada", "por_hora", "cami_and_co", 0, None),
]


class Command(BaseCommand):
    help = "Upsert Tarifa records for Cami&Co and Rangers Academy"

    def handle(self, *args, **options):
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("No users found — create a user first."))
            return

        for nombre, tipo_cobro, marca, precio, horas_semanales in SEED_ROWS:
            tarifa, created = Tarifa.objects.get_or_create(
                academia=user,
                nombre=nombre,
                tipo_cobro=tipo_cobro,
                marca=marca,
                horas_semanales=horas_semanales,
                defaults={"precio": precio},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created {tarifa}"))
            elif tarifa.precio != precio:
                tarifa.precio = precio
                tarifa.save(update_fields=["precio"])
                self.stdout.write(self.style.SUCCESS(f"Updated price for {tarifa}"))
            else:
                self.stdout.write(f"{tarifa} already up to date")
