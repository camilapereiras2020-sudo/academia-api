from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from modules.tarifas.models import Tarifa
from modules.tarifas import pricing

User = get_user_model()

# (nombre, tipo_cobro, marca, precio, horas_semanales)
# clase_grupo/bono_familia mensual (1-3h/sem) sale de pricing.py — la misma
# tarifa oficial 60 min que calcula la ficha del alumno — en vez de un
# número aparte: se habían desincronizado (48/90/135 y 90/175/260 acá vs.
# 50/95/145 y 95/180/275 en pricing.py), por eso NuevoPagoPage mostraba un
# importe de Tarifa distinto al real de la clase (ver Grupo.tarifa, que es
# lo que de verdad cobra cada clase — esto solo alimenta el desplegable
# "Tarifa" de Nuevo Pago, informativo).
SEED_ROWS = [
    # Rangers Academy — fixed rates (60 min; pricing.py no cubre 90 min con
    # un horas_semanales 1-3 limpio, así que esas tarifas quedan sin fila aquí)
    ("clase_grupo", "por_hora", "rangers_academy", 12, None),
    ("clase_grupo", "mensual", "rangers_academy", pricing.CLASES_GRUPO[60][1], 1),
    ("clase_grupo", "mensual", "rangers_academy", pricing.CLASES_GRUPO[60][2], 2),
    ("clase_grupo", "mensual", "rangers_academy", pricing.CLASES_GRUPO[60][3], 3),
    ("bono_familia", "mensual", "rangers_academy", pricing.BONO_FAMILIA[60][1], 1),
    ("bono_familia", "mensual", "rangers_academy", pricing.BONO_FAMILIA[60][2], 2),
    ("bono_familia", "mensual", "rangers_academy", pricing.BONO_FAMILIA[60][3], 3),
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
