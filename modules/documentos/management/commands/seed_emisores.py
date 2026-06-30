from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from modules.documentos.models import Emisor

User = get_user_model()


class Command(BaseCommand):
    help = "Seed Emisor records for Cami&Co and Rangers Academy"

    def handle(self, *args, **options):
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("No users found. Create a user first."))
            return

        camiandco, created = Emisor.objects.update_or_create(
            slug="camiandco",
            defaults=dict(
                academia         = user,
                nombre           = "Cami&Co",
                autonoma         = "Camila Pereiras Casal",
                nif              = "39468659S",
                direccion        = "C/ Pedro Soto Couselo 5, 2ºB",
                ciudad           = "36995, Poio (Pontevedra)",
                telefono         = "698183419",
                iban             = "ES10 2080 5020 0530 4003 9725",
                factura_prefix   = "CC",
                recibo_prefix    = "RE",
                factura_baseline = 236,
                recibo_baseline  = 236,
                drive_folder_id  = "",
                activo           = True,
            ),
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} Cami&Co emisor (id={camiandco.id})"))

        rangers, created = Emisor.objects.update_or_create(
            slug="rangers",
            defaults=dict(
                academia         = user,
                nombre           = "Rangers Academy",
                autonoma         = "Candela Pereiras Casal",
                nif              = "39468660Q",
                direccion        = "C/ Herreros 26",
                ciudad           = "36002, Pontevedra",
                telefono         = "613014124",
                iban             = "",
                factura_prefix   = "RA",
                recibo_prefix    = "RR",
                factura_baseline = 0,
                recibo_baseline  = 0,
                drive_folder_id  = "",
                activo           = False,
            ),
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} Rangers Academy emisor (id={rangers.id})"))
        self.stdout.write(self.style.WARNING(
            "Rangers Academy is inactive (activo=False). "
            "Set factura_baseline, recibo_baseline, drive_folder_id, and activo=True when ready."
        ))
