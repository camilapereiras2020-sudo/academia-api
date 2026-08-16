from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from modules.niveles.models import Nivel

User = get_user_model()

# (categoria, nombre) in display order
SEED_ROWS = [
    ("kids", "Pre-A1 Starters"),
    ("kids", "A1 Movers"),
    ("kids", "A2 Flyers"),
    ("kids", "A2+ Key for Schools"),
    ("kids", "B1 Preliminary for Schools"),

    ("teens", "A2 Key"),
    ("teens", "B1 Preliminary"),
    ("teens", "B2 First FCE"),
    ("teens", "C1 Advanced CAE"),

    ("adults", "A1 Beginner"),
    ("adults", "A2 Elementary"),
    ("adults", "B1 Intermediate"),
    ("adults", "B2 Upper Intermediate"),
    ("adults", "C1 Advanced CAE"),
    ("adults", "C2 Proficiency CPE"),
]


class Command(BaseCommand):
    help = "Upsert the default Nivel records (kids/teens/adults)"

    def handle(self, *args, **options):
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("No users found — create a user first."))
            return

        ordenes = {}
        for categoria, nombre in SEED_ROWS:
            orden = ordenes.get(categoria, 0)
            ordenes[categoria] = orden + 1

            nivel, created = Nivel.objects.get_or_create(
                academia=user, categoria=categoria, nombre=nombre,
                defaults={"orden": orden, "activo": True},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created {nivel}"))
            elif nivel.orden != orden:
                nivel.orden = orden
                nivel.save(update_fields=["orden"])
                self.stdout.write(self.style.SUCCESS(f"Updated orden for {nivel}"))
            else:
                self.stdout.write(f"{nivel} already up to date")
