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
    # Cada enero el contador vuelve a su baseline: 0 = la numeración empieza de
    # cero en enero (antes 236, que era el punto de partida de 2026). No afecta al
    # año en curso: el contador de 2026 sigue donde está.
    factura_baseline = 0,
    recibo_baseline  = 0,
    recibo_efectivo_suffix   = "C",
    recibo_efectivo_baseline = 199,
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
    recibo_efectivo_suffix   = "R",
    recibo_efectivo_baseline = 299,
    drive_folder_id  = "17xDVHjzwsvaRIVhSiNAVLlFeNF-d7tF-",
    activo           = True,
)


# Datos que se editan desde Configuración → Datos de facturación (ver
# EmisorSerializer). Como este comando corre en CADA despliegue (Procfile), solo
# los rellena cuando están vacíos: antes los sobrescribía siempre y un IBAN (o
# una dirección) escrito en la app se perdía en el siguiente deploy.
EDITABLES_EN_LA_APP = {"nombre", "autonoma", "nif", "direccion", "ciudad", "telefono", "email", "iban"}


class Command(BaseCommand):
    help = "Upsert Emisor records for Cami&Co and Rangers Academy (no pisa lo escrito en la app)"

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
                # Update the structural fields (prefixes, baselines, activo…) always;
                # the editable ones only when empty; never an existing drive_folder_id.
                changed = []
                for field, val in data.items():
                    if field == "drive_folder_id" and emisor.drive_folder_id:
                        continue  # never overwrite a folder ID that's already set
                    if field in EDITABLES_EN_LA_APP and getattr(emisor, field):
                        continue  # lo escrito en la app manda
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
