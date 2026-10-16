"""fix_missing_invoices respeta el modo cuarentena y no duplica facturas combinadas."""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from modules.alumnos.models import Alumno
from modules.documentos import cuarentena
from modules.documentos.models import Documento, Emisor
from modules.pagadores.models import Pagador
from modules.pagos.models import Pago

User = get_user_model()


class FixMissingInvoicesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", email="o@example.com", password="x")
        self.emisor = Emisor.objects.create(
            academia=self.user, slug="camiandco", nombre="Cami&Co", autonoma="C", nif="X1",
            direccion="X", ciudad="X", factura_prefix="CC", recibo_prefix="RE",
            drive_folder_id="FOLDER",
        )
        self.pagador = Pagador.objects.create(academia=self.user, nombre="Mamá")

    def pago(self, nombre="Hijo"):
        al = Alumno.objects.create(academia=self.user, nombre=nombre, marca="cami_and_co", pagador=self.pagador)
        return Pago.objects.create(
            academia=self.user, marca="cami_and_co", emisor=self.emisor, pagador=self.pagador, alumno=al,
            periodo="2026-10", fecha="2026-10-01", mensualidad=80, descuento=0, extras=[], total=80,
            metodo="transferencia", estado="pagado", estado_carga="completo",
        )

    def correr(self, *args):
        out = StringIO()
        call_command("fix_missing_invoices", *args, stdout=out)
        return out.getvalue()

    def activar(self):
        self.user.modo_cuarentena = True
        self.user.save()

    @patch("modules.documentos.management.commands.fix_missing_invoices.generate_invoice_for_pago",
           return_value=("CC1-26", "DRIVE_ID", "factura"))
    def test_modo_apagado_emite_como_siempre(self, gen):
        p = self.pago()
        self.correr()
        gen.assert_called_once()
        d = Documento.objects.get(pago=p)
        self.assertEqual((d.estado, d.num_doc, d.s3_key), ("emitida", "CC1-26", "DRIVE_ID"))

    @patch("modules.documentos.management.commands.fix_missing_invoices.generate_invoice_for_pago")
    def test_modo_activo_crea_documento_en_cuarentena_sin_numero_ni_drive(self, gen):
        self.activar()
        self.emisor.drive_folder_id = ""   # la cuarentena no necesita Drive
        self.emisor.save()
        p = self.pago()
        self.correr()
        gen.assert_not_called()
        d = Documento.objects.get(pago=p)
        self.assertEqual((d.estado, d.num_doc, d.s3_key), ("cuarentena", "", ""))
        self.emisor.refresh_from_db()
        self.assertEqual((self.emisor.factura_counter, self.emisor.recibo_counter), (0, 0))
        p.refresh_from_db()
        self.assertEqual(p.num_doc, "")

    @patch("modules.documentos.management.commands.fix_missing_invoices.generate_invoice_for_pago")
    def test_modo_activo_dry_run_no_crea_nada(self, gen):
        self.activar()
        self.pago()
        salida = self.correr("--dry-run")
        self.assertIn("would send to cuarentena", salida)
        gen.assert_not_called()
        self.assertEqual(Documento.objects.count(), 0)

    @patch("modules.documentos.management.commands.fix_missing_invoices.generate_invoice_for_pago")
    def test_segunda_ejecucion_no_duplica(self, gen):
        self.activar()
        self.pago()
        self.correr()
        self.correr()
        self.assertEqual(Documento.objects.count(), 1)

    @patch("modules.documentos.management.commands.fix_missing_invoices.generate_invoice_for_pago")
    def test_pagos_de_una_factura_combinada_no_se_tocan(self, gen):
        self.activar()
        a, b = self.pago("Hijo A"), self.pago("Hijo B")
        doc, _ = cuarentena.crear_documento_cuarentena(self.user, [a, b])
        self.assertEqual(Documento.objects.count(), 1)
        self.correr()
        gen.assert_not_called()
        self.assertEqual(Documento.objects.count(), 1)   # B no recibe un documento propio
        self.assertEqual(list(doc.pagos_adicionales.all()), [b])

    @patch("modules.documentos.management.commands.fix_missing_invoices.generate_invoice_for_pago",
           return_value=("CC1-26", "DRIVE_ID", "factura"))
    def test_modo_apagado_tampoco_duplica_combinadas(self, gen):
        a, b = self.pago("Hijo A"), self.pago("Hijo B")
        doc = Documento.objects.create(
            academia=self.user, pago=a, tipo="factura", nombre="CC9-26.pdf", num_doc="CC9-26", estado="emitida",
        )
        doc.pagos_adicionales.set([b])
        self.correr()
        gen.assert_not_called()
        self.assertEqual(Documento.objects.count(), 1)
