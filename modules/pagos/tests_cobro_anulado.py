"""Anular un documento obliga a decidir (explícitamente) si el dinero se cobró."""
import importlib
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from modules.alumnos.models import Alumno
from modules.documentos.models import Documento, Emisor
from modules.grupos.models import Grupo
from modules.pagadores.models import Pagador
from modules.pagos.models import Pago

User = get_user_model()


@patch("modules.documentos.sheets_log.log_anulacion")
@patch("modules.documentos.invoice_service.regenerate_anulada_pdf", return_value="DRIVE")
class CobroAnuladoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", email="o@example.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.emisor = Emisor.objects.create(
            academia=self.user, slug="camiandco", nombre="Cami&Co", autonoma="C", nif="X1",
            direccion="X", ciudad="X", factura_prefix="CC", recibo_prefix="RE",
        )
        self.pagador = Pagador.objects.create(academia=self.user, nombre="Mamá")
        self.grupo = Grupo.objects.create(academia=self.user, marca="cami_and_co", nombre="G", nivel="A1", tarifa=60)

    def pago(self, nombre="Hijo", estado="pagado"):
        al = Alumno.objects.create(academia=self.user, nombre=nombre, marca="cami_and_co", pagador=self.pagador)
        return Pago.objects.create(
            academia=self.user, marca="cami_and_co", emisor=self.emisor, pagador=self.pagador,
            alumno=al, grupo=self.grupo, periodo="2026-10", fecha="2026-10-01", mensualidad=60,
            descuento=0, extras=[], total=60, metodo="transferencia", estado=estado, estado_carga="completo",
        )

    def doc(self, pago, num="CC-1", adicionales=()):
        d = Documento.objects.create(
            academia=self.user, pago=pago, emisor=self.emisor, tipo="factura", nombre=f"{num}.pdf",
            num_doc=num, estado="emitida",
        )
        d.pagos_adicionales.set(adicionales)
        return d

    def anular_doc(self, d, **extra):
        return self.client.post(f"/api/v1/documentos/{d.id}/anular/", {"motivo_anulacion": "error", **extra}, format="json")

    def test_sin_respuesta_explicita_no_anula_nada(self, m_pdf, m_log):
        p = self.pago()
        d = self.doc(p)
        r = self.anular_doc(d)
        self.assertEqual(r.status_code, 400)
        d.refresh_from_db(); p.refresh_from_db()
        self.assertEqual((d.estado, p.estado), ("emitida", "pagado"))

    def test_cobrado_si_anula_solo_el_documento(self, m_pdf, m_log):
        p = self.pago(); d = self.doc(p)
        r = self.anular_doc(d, anular_cobro=False)
        self.assertEqual(r.status_code, 200)
        d.refresh_from_db(); p.refresh_from_db()
        self.assertEqual((d.estado, p.estado), ("anulada", "pagado"))

    def test_no_cobrado_anula_tambien_el_cobro(self, m_pdf, m_log):
        p = self.pago(); d = self.doc(p)
        r = self.anular_doc(d, anular_cobro=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["cobro_anulado"], 1)
        p.refresh_from_db()
        self.assertEqual(p.estado, "anulado")
        self.assertEqual(p.motivo_anulacion, "error")
        self.assertEqual(p.anulado_por, self.user)
        self.assertIsNotNone(p.anulado_at)

    def test_cobro_anulado_no_cuenta_en_pagadores(self, m_pdf, m_log):
        p = self.pago(); d = self.doc(p)
        self.anular_doc(d, anular_cobro=True)
        r = self.client.get("/api/v1/pagadores/calculadora/?periodo=2026-10")
        if r.status_code == 200:
            self.assertEqual(r.data[0]["estado_pago"], "sin_generar")

    def test_documento_combinado_anula_todos_los_cobros(self, m_pdf, m_log):
        p1, p2 = self.pago("A"), self.pago("B")
        d = self.doc(p1, adicionales=[p2])
        r = self.anular_doc(d, anular_cobro=True)
        self.assertEqual(r.data["cobro_anulado"], 2)
        self.assertEqual(Pago.objects.filter(estado="anulado").count(), 2)

    def test_pago_anular_exige_respuesta_y_la_aplica(self, m_pdf, m_log):
        p = self.pago(); self.doc(p)
        url = f"/api/v1/pagos/{p.id}/anular/"
        self.assertEqual(self.client.post(url, {"motivo_anulacion": "x"}, format="json").status_code, 400)
        r = self.client.post(url, {"motivo_anulacion": "x", "anular_cobro": True}, format="json")
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.estado, "anulado")

    def test_no_se_puede_poner_anulado_a_mano(self, m_pdf, m_log):
        p = self.pago()
        r = self.client.patch(f"/api/v1/pagos/{p.id}/", {"estado": "anulado"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_marcar_pagado_rechaza_anulado_y_restaurar_exige_respuesta(self, m_pdf, m_log):
        p = self.pago(estado="anulado")
        self.assertEqual(self.client.post(f"/api/v1/pagos/{p.id}/marcar-pagado/").status_code, 409)
        url = f"/api/v1/pagos/{p.id}/restaurar-cobro/"
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 400)
        r = self.client.post(url, {"cobrado": True}, format="json")
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.estado, "pagado")

    def test_borrar_pago_anulado_conserva_documentos_anulados(self, m_pdf, m_log):
        p = self.pago(); d = self.doc(p)
        self.anular_doc(d, anular_cobro=True)
        r = self.client.delete(f"/api/v1/pagos/{p.id}/")
        self.assertEqual(r.status_code, 204)
        self.assertTrue(Pago.objects.filter(id=p.id, borrado_at__isnull=False).exists())
        self.assertTrue(Documento.objects.filter(id=d.id, estado="anulada").exists())
        self.assertNotIn(p.id, [x["id"] for x in self.client.get("/api/v1/pagos/").data])
        self.assertIn(p.id, [x["id"] for x in self.client.get("/api/v1/pagos/?borrados=1").data])

    def test_no_se_borra_pago_con_documento_vigente(self, m_pdf, m_log):
        p = self.pago(estado="anulado"); self.doc(p)
        self.assertEqual(self.client.delete(f"/api/v1/pagos/{p.id}/").status_code, 409)

    def test_pago_cobrado_con_documento_emitido_no_se_borra(self, m_pdf, m_log):
        p = self.pago(); self.doc(p)
        self.assertEqual(self.client.delete(f"/api/v1/pagos/{p.id}/").status_code, 409)

    def test_migracion_marca_pagos_con_documento_anulado(self, m_pdf, m_log):
        p1 = self.pago("A"); d1 = self.doc(p1, "CC-1")
        Documento.objects.filter(id=d1.id).update(estado="anulada")
        p2 = self.pago("B"); self.doc(p2, "CC-2")
        mod = importlib.import_module("modules.pagos.migrations.0011_migrar_cobros_con_documento_anulado")
        mod.migrar(apps, None)
        p1.refresh_from_db(); p2.refresh_from_db()
        self.assertEqual((p1.estado, p2.estado), ("anulado", "pagado"))
