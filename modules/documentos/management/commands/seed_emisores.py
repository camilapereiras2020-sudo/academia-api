from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from modules.documentos.models import Emisor

User = get_user_model()

CAMIANDCO = dict(
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
    drive_folder_id  = "1W3Jt5XMelFeUa_W4Gr8r381R4Gaz1imn",
    activo           = True,
)

RANGERS = dict(
    nombre           = "Rangers Academy",
    autonoma         = "Candela Pereiras Casal",
    nif              = "39468660Q",
    direccion        = "Rúa dos Ferreiros, 26",
    ciudad           = "36002 Pontevedra",
    telefono         = "613 014 124",
    email            = "info@rangersacademy.es",
    iban             = "",
    factura_prefix   = "RA",
    recibo_prefix    = "RR",
    factura_baseline = 0,
    recibo_baseline  = 0,
    drive_folder_id  = "17xDVHjzwsvaRIVhSiNAVLlFeNF-d7tF-",
    activo           = True,
)


class Command(BaseCommand):
    help = "Upsert Emisor records for Cami&Co and Rangers Academy"

    def handle(self, *args, **options):
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("No users found — create a user first."))
            return

        for slug, data in [("camiandco", CAMIANDCO), ("rangers", RANGERS)]:
            emisor, created = Emisor.objects.get_or_create(
                slug=slug,
                defaults=dict(academia=user, **data),
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created {slug} emisor (id={emisor.id})"))
            else:
                # Update everything EXCEPT drive_folder_id if it's already set to a real value
                changed = []
                for field, val in data.items():
                    if field == "drive_folder_id" and emisor.drive_folder_id:
                        continue  # never overwrite a folder ID that's already set
                    if getattr(emisor, field) != val:
                        setattr(emisor, field, val)
                        changed.append(field)
                if changed:
                    emisor.save(update_fields=changed)
                    self.stdout.write(self.style.SUCCESS(
                        f"Updated {slug} emisor (id={emisor.id}): {changed}"
                    ))
                else:
                    self.stdout.write(f"{slug} emisor already up to date (id={emisor.id})")
