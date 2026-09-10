"""Tests for combined ("family") invoicing — generar-combinado bundles
several Pagos (siblings sharing one pagador) onto a single Documento.
Every external side effect (Drive upload, Sheets log) is mocked, matching
the pattern in modules.pagos.tests — never touches real infrastructure.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from modules.alumnos.models import Alumno
from modules.pagadores.models import Pagador
from modules.grupos.models import Grupo
from modules.documentos.models import Emisor, Documento
from modules.pagos.models import Pago

User = get_user_model()


class CombinedInvoiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.emisor_cami = Emisor.objects.create(
            academia=self.user, slug="camiandco", nombre="Cami&Co",
            autonoma="Cami", nif="X1", direccion="X", ciudad="X",
            factura_prefix="CC", recibo_prefix="RE",
        )
        self.emisor_rangers = Emisor.objects.create(
            academia=self.user, slug="rangers", nombre="Rangers Academy",
            autonoma="Cande", nif="X2", direccion="X", ciudad="X",
            factura_prefix="RA", recibo_prefix="RR",
        )
        self.pagador = Pagador.objects.create(academia=self.user, nombre="Mamá Troncoso")

        self.grupo_cami = Grupo.objects.create(
            academia=self.user, marca="cami_and_co", nombre="Cami Kids", nivel="A1", tarifa=80,
        )
        self.grupo_rangers = Grupo.objects.create(
            academia=self.user, marca="rangers_academy", nombre="Rangers Kids", nivel="A1", tarifa=80,
        )

        self.hijo1 = Alumno.objects.create(academia=self.user, nombre="Hijo Uno", marca="rangers_academy", pagador=self.pagador)
        self.hijo2 = Alumno.objects.create(academia=self.user, nombre="Hijo Dos", marca="cami_and_co", pagador=self.pagador)
        self.hijo3 = Alumno.objects.create(academia=self.user, nombre="Hijo Tres", marca="rangers_academy", pagador=self.pagador)
        self.hijo1.grupos.add(self.grupo_rangers)
        self.hijo2.grupos.add(self.grupo_cami)
        self.hijo3.grupos.add(self.grupo_rangers)

        def _pago(alumno, marca, emisor, total=80):
            return Pago.objects.create(
                academia=self.user, marca=marca, emisor=emisor,
                pagador=self.pagador, alumno=alumno,
                grupo=alumno.grupos.first(),
                periodo="2026-09", fecha="2026-09-01",
                mensualidad=total, descuento=0, extras=[], total=total,
                metodo="transferencia", estado="pagado", estado_carga="completo",
            )

        self.pago1 = _pago(self.hijo1, "rangers_academy", self.emisor_rangers)
        self.pago2 = _pago(self.hijo2, "cami_and_co", self.emisor_cami)
        self.pago3 = _pago(self.hijo3, "rangers_academy", self.emisor_rangers)

    @patch("modules.documentos.sheets_log.log_emision")
    @patch("modules.documentos.invoice_service.upload_to_drive")
    def test_combine_same_emisor_pagos_no_override_needed(self, mock_upload, mock_log):
        """Two Rangers-brand siblings, same emisor already on both pagos —
        no explicit emisor_id required."""
        mock_upload.return_value = "FAKE_DRIVE_ID"
        resp = self.client.post(
            "/api/v1/documentos/generar-combinado/",
            {"pago_ids": [self.pago1.id, self.pago3.id]},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(data["pago"], self.pago1.id)
        self.assertEqual(set(data["pagos_adicionales"]), {self.pago3.id})
        self.assertTrue(data["num_doc"].startswith("RA"))
        self.assertEqual(data["pago_info"]["total"], "160.00")
        self.assertEqual(set(data["pago_info"]["alumnos"]), {"Hijo Uno", "Hijo Tres"})

        self.pago1.refresh_from_db()
        self.pago3.refresh_from_db()
        self.assertEqual(self.pago1.num_doc, data["num_doc"])
        self.assertEqual(self.pago3.num_doc, data["num_doc"])

    @patch("modules.documentos.sheets_log.log_emision")
    @patch("modules.documentos.invoice_service.upload_to_drive")
    def test_combine_mixed_marca_requires_explicit_emisor(self, mock_upload, mock_log):
        """Sibling split across both brands: refuses to guess which sister invoices."""
        resp = self.client.post(
            "/api/v1/documentos/generar-combinado/",
            {"pago_ids": [self.pago1.id, self.pago2.id]},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("emisor", resp.json()["error"].lower())

    @patch("modules.documentos.sheets_log.log_emision")
    @patch("modules.documentos.invoice_service.upload_to_drive")
    def test_combine_mixed_marca_with_explicit_emisor_succeeds(self, mock_upload, mock_log):
        """The sisters' actual arrangement: one of them (their choice, via
        emisor_id) invoices the whole family regardless of which brand each
        kid's class happens to be under."""
        mock_upload.return_value = "FAKE_DRIVE_ID"
        resp = self.client.post(
            "/api/v1/documentos/generar-combinado/",
            {"pago_ids": [self.pago1.id, self.pago2.id], "emisor_id": self.emisor_cami.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertTrue(data["num_doc"].startswith("CC"))
        self.assertEqual(set(data["pago_info"]["alumnos"]), {"Hijo Uno", "Hijo Dos"})

    def test_combine_different_pagador_rejected(self):
        otro_pagador = Pagador.objects.create(academia=self.user, nombre="Otro Pagador")
        otro_alumno = Alumno.objects.create(academia=self.user, nombre="Otro Hijo", marca="rangers_academy", pagador=otro_pagador)
        otro_pago = Pago.objects.create(
            academia=self.user, marca="rangers_academy", emisor=self.emisor_rangers,
            pagador=otro_pagador, alumno=otro_alumno,
            periodo="2026-09", fecha="2026-09-01",
            mensualidad=80, descuento=0, extras=[], total=80,
            metodo="transferencia", estado="pagado", estado_carga="completo",
        )
        resp = self.client.post(
            "/api/v1/documentos/generar-combinado/",
            {"pago_ids": [self.pago1.id, otro_pago.id]},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("mismo pagador", resp.json()["error"])

    def test_combine_requires_at_least_two_pagos(self):
        resp = self.client.post(
            "/api/v1/documentos/generar-combinado/",
            {"pago_ids": [self.pago1.id]},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.content)

    @patch("modules.documentos.sheets_log.log_emision")
    @patch("modules.documentos.invoice_service.upload_to_drive")
    def test_combine_twice_rejected_already_invoiced(self, mock_upload, mock_log):
        mock_upload.return_value = "FAKE_DRIVE_ID"
        resp1 = self.client.post(
            "/api/v1/documentos/generar-combinado/",
            {"pago_ids": [self.pago1.id, self.pago3.id]},
            format="json",
        )
        self.assertEqual(resp1.status_code, 201, resp1.content)

        resp2 = self.client.post(
            "/api/v1/documentos/generar-combinado/",
            {"pago_ids": [self.pago1.id, self.pago3.id]},
            format="json",
        )
        self.assertEqual(resp2.status_code, 400, resp2.content)

    @patch("modules.documentos.sheets_log.log_emision")
    @patch("modules.documentos.invoice_service.upload_to_drive")
    def test_deleting_additional_pago_blocked_after_combined_invoice(self, mock_upload, mock_log):
        """pago3 is only ever the *additional* side of the combined
        Documento (pago1 is primary) — must still be protected from
        deletion, since the M2M side gets no DB-level on_delete guard."""
        mock_upload.return_value = "FAKE_DRIVE_ID"
        resp = self.client.post(
            "/api/v1/documentos/generar-combinado/",
            {"pago_ids": [self.pago1.id, self.pago3.id]},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        del_resp = self.client.delete(f"/api/v1/pagos/{self.pago3.id}/")
        self.assertEqual(del_resp.status_code, 409, del_resp.content)
        self.assertTrue(Pago.objects.filter(id=self.pago3.id).exists())

    @patch("modules.documentos.sheets_log.log_emision")
    @patch("modules.documentos.invoice_service.upload_to_drive")
    def test_single_pago_invoice_path_unaffected(self, mock_upload, mock_log):
        """Sanity check: the ordinary single-pago /generar/ endpoint still
        works exactly as before, untouched by any of the above."""
        mock_upload.return_value = "FAKE_DRIVE_ID"
        resp = self.client.post(
            "/api/v1/documentos/generar/",
            {"pago_id": self.pago1.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(data["pagos_adicionales"], [])
        self.assertEqual(data["pago_info"]["alumnos"], ["Hijo Uno"])
