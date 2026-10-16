"""seed_emisores corre en cada despliegue: no debe pisar lo escrito en la app."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from modules.documentos.models import Emisor

User = get_user_model()


class SeedEmisoresTests(TestCase):
    def setUp(self):
        User.objects.create_user(username="owner", email="o@example.com", password="x")

    def seed(self):
        call_command("seed_emisores", stdout=StringIO())

    def test_primera_ejecucion_crea_los_dos_emisores(self):
        self.seed()
        self.assertEqual(set(Emisor.objects.values_list("slug", flat=True)), {"camiandco", "rangers"})

    def test_el_iban_escrito_en_la_app_sobrevive_al_siguiente_despliegue(self):
        self.seed()
        Emisor.objects.filter(slug="rangers").update(iban="ES00 1111 2222 3333 4444 5555")
        self.seed()   # = otro despliegue
        self.assertEqual(Emisor.objects.get(slug="rangers").iban, "ES00 1111 2222 3333 4444 5555")

    def test_direccion_telefono_y_nombre_editados_sobreviven(self):
        self.seed()
        Emisor.objects.filter(slug="camiandco").update(direccion="Nueva calle 1", telefono="600000000", nombre="Cami & Co S.L.")
        self.seed()
        e = Emisor.objects.get(slug="camiandco")
        self.assertEqual((e.direccion, e.telefono, e.nombre), ("Nueva calle 1", "600000000", "Cami & Co S.L."))

    def test_un_dato_vacio_si_se_rellena_desde_el_seed(self):
        self.seed()
        Emisor.objects.filter(slug="rangers").update(email="")
        self.seed()
        self.assertEqual(Emisor.objects.get(slug="rangers").email, "info@rangersacademy.es")

    def test_lo_estructural_si_se_sigue_imponiendo(self):
        """Prefijos y baselines de la numeración no se editan en la app: el seed los mantiene."""
        self.seed()
        Emisor.objects.filter(slug="rangers").update(factura_prefix="XX", recibo_baseline=999)
        self.seed()
        e = Emisor.objects.get(slug="rangers")
        self.assertEqual((e.factura_prefix, e.recibo_baseline), ("RA", 0))

    def test_no_toca_contadores_ni_la_carpeta_de_drive(self):
        self.seed()
        Emisor.objects.filter(slug="camiandco").update(factura_counter=57, factura_counter_year=2026, drive_folder_id="MI_CARPETA")
        self.seed()
        e = Emisor.objects.get(slug="camiandco")
        self.assertEqual((e.factura_counter, e.factura_counter_year, e.drive_folder_id), (57, 2026, "MI_CARPETA"))
