"""Flujo recibo → factura: el recibo nace solo al cobrar; la factura es manual."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from modules.alumnos.models import Alumno
from modules.documentos.models import Documento, Emisor
from modules.pagadores.models import Pagador
from modules.pagos.models import Pago

User = get_user_model()


@patch("modules.documentos.sheets_log.log_anulacion")
@patch("modules.documentos.sheets_log.log_emision")
@patch("modules.documentos.invoice_service.regenerate_anulada_pdf", return_value="DRIVE")
@patch("modules.documentos.cuarentena.upload_to_drive", return_value="DRIVE")
class ReciboFacturaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", email="o@example.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cami = Emisor.objects.create(
            academia=self.user, slug="camiandco", nombre="Cami&Co", autonoma="C", nif="X1",
            direccion="X", ciudad="X", factura_prefix="CC", recibo_prefix="RC",
        )
        self.pagador = Pagador.objects.create(academia=self.user, nombre="Mamá")

    def alumno(self, nombre="Hijo"):
        return Alumno.objects.create(academia=self.user, nombre=nombre, marca="cami_and_co", pagador=self.pagador)

    def crear_pago(self, estado="pagado", nombre="Hijo", alumno=True, metodo="transferencia"):
        data = {
            "marca": "cami_and_co", "periodo": "2026-10", "fecha": "2026-10-01", "mensualidad": 60,
            "descuento": 0, "extras": [], "total": 60, "metodo": metodo, "estado": estado,
        }
        if alumno:
            data.update(alumno=self.alumno(nombre).id, pagador=self.pagador.id)
        r = self.client.post("/api/v1/pagos/", data, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return Pago.objects.get(id=r.json()["id"])

    def confirmar(self, doc):
        r = self.client.post("/api/v1/documentos/confirmar/", {"ids": [doc.id]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        doc.refresh_from_db()
        return doc

    # ── recibo automático ───────────────────────────────────────────────
    def test_pago_cobrado_crea_su_recibo_provisional_aunque_sea_transferencia(self, *m):
        p = self.crear_pago("pagado", metodo="transferencia")
        d = p.documentos.get()
        self.assertEqual((d.tipo, d.estado, d.num_doc), ("recibo", "cuarentena", ""))

    def test_pago_pendiente_no_crea_recibo_y_al_cobrarlo_si(self, *m):
        p = self.crear_pago("pendiente")
        self.assertFalse(p.documentos.exists())
        self.assertEqual(self.client.post(f"/api/v1/pagos/{p.id}/marcar-pagado/").status_code, 200)
        self.assertEqual(p.documentos.count(), 1)
        self.client.post(f"/api/v1/pagos/{p.id}/marcar-pagado/")   # idempotente
        self.assertEqual(p.documentos.count(), 1)

    def test_restaurar_cobro_como_cobrado_crea_recibo(self, *m):
        p = self.crear_pago("pendiente")
        Pago.objects.filter(pk=p.pk).update(estado="anulado")
        r = self.client.post(f"/api/v1/pagos/{p.id}/restaurar-cobro/", {"cobrado": False}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(p.documentos.exists())
        Pago.objects.filter(pk=p.pk).update(estado="anulado")
        self.client.post(f"/api/v1/pagos/{p.id}/restaurar-cobro/", {"cobrado": True}, format="json")
        self.assertEqual(p.documentos.count(), 1)

    def test_pago_incompleto_se_guarda_sin_recibo_y_sin_error(self, *m):
        p = self.crear_pago("pagado", alumno=False)
        self.assertEqual(p.estado, "pagado")
        self.assertFalse(p.documentos.exists())

    def test_generar_manual_exige_pago_cobrado(self, *m):
        p = self.crear_pago("pendiente")
        r = self.client.post("/api/v1/documentos/generar/", {"pago_id": p.id}, format="json")
        self.assertEqual(r.status_code, 400)

    # ── Bono Familia: un solo recibo combinado ──────────────────────────
    def test_bono_familia_hermanos_comparten_un_recibo_combinado(self, *m):
        with patch("modules.documentos.auto_recibo._es_bono_familia", return_value=True):
            a = self.crear_pago("pagado", "A")
            b = self.crear_pago("pagado", "B")
        self.assertEqual(Documento.objects.count(), 1)
        d = Documento.objects.get()
        self.assertEqual({p.id for p in d.todos_los_pagos()}, {a.id, b.id})

    def test_bono_familia_con_el_recibo_ya_confirmado_el_hermano_tiene_el_suyo(self, *m):
        with patch("modules.documentos.auto_recibo._es_bono_familia", return_value=True):
            a = self.crear_pago("pagado", "A")
            self.confirmar(a.documentos.get())
            self.crear_pago("pagado", "B")
        self.assertEqual(Documento.objects.count(), 2)

    def test_sin_bono_familia_cada_pago_su_recibo(self, *m):
        with patch("modules.documentos.auto_recibo._es_bono_familia", return_value=False):
            self.crear_pago("pagado", "A")
            self.crear_pago("pagado", "B")
        self.assertEqual(Documento.objects.count(), 2)

    # ── factura manual desde un recibo confirmado ───────────────────────
    def test_factura_solo_desde_recibo_confirmado(self, *m):
        recibo = self.crear_pago().documentos.get()
        r = self.client.post(f"/api/v1/documentos/{recibo.id}/generar-factura/")
        self.assertEqual(r.status_code, 400)   # aún provisional
        self.confirmar(recibo)
        r = self.client.post(f"/api/v1/documentos/{recibo.id}/generar-factura/")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()["tipo"], r.json()["estado"], r.json()["recibo_origen"]), ("factura", "cuarentena", recibo.id))
        again = self.client.post(f"/api/v1/documentos/{recibo.id}/generar-factura/")
        self.assertEqual((again.status_code, again.json()["id"]), (200, r.json()["id"]))

    def test_confirmar_factura_numera_con_cc_y_no_toca_el_numero_del_recibo(self, *m):
        p = self.crear_pago()
        recibo = self.confirmar(p.documentos.get())
        self.assertEqual(recibo.num_doc, "RC1-26")
        f = Documento.objects.get(id=self.client.post(f"/api/v1/documentos/{recibo.id}/generar-factura/").json()["id"])
        f = self.confirmar(f)
        self.assertEqual((f.tipo, f.num_doc), ("factura", "CC1-26"))
        p.refresh_from_db(); self.cami.refresh_from_db()
        self.assertEqual(p.num_doc, "RC1-26")           # el pago sigue mostrando su recibo
        self.assertEqual((self.cami.recibo_counter, self.cami.factura_counter), (1, 1))

    def test_no_se_puede_hacer_factura_de_una_factura(self, *m):
        recibo = self.confirmar(self.crear_pago().documentos.get())
        f = self.confirmar(Documento.objects.get(id=self.client.post(f"/api/v1/documentos/{recibo.id}/generar-factura/").json()["id"]))
        self.assertEqual(self.client.post(f"/api/v1/documentos/{f.id}/generar-factura/").status_code, 400)

    # ── anular ──────────────────────────────────────────────────────────
    def anular(self, doc, cobro, motivo="x"):
        return self.client.post(
            f"/api/v1/documentos/{doc.id}/anular/", {"motivo_anulacion": motivo, "anular_cobro": cobro}, format="json"
        )

    def test_recibo_con_factura_vigente_no_se_anula_hasta_anular_la_factura(self, *m):
        recibo = self.confirmar(self.crear_pago().documentos.get())
        f = self.confirmar(Documento.objects.get(id=self.client.post(f"/api/v1/documentos/{recibo.id}/generar-factura/").json()["id"]))
        self.assertEqual(self.anular(recibo, False).status_code, 409)
        # anular la factura nunca anula el cobro: el recibo lo sostiene
        self.assertEqual(self.anular(f, True).status_code, 400)
        self.assertEqual(self.anular(f, False).status_code, 200)
        # ya sin factura vigente, el recibo sí se puede anular (y con él el cobro)
        r = self.anular(recibo, True)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Pago.objects.get(pk=recibo.pago_id).estado, "anulado")

    def test_factura_anulada_permite_generar_otra(self, *m):
        recibo = self.confirmar(self.crear_pago().documentos.get())
        f = self.confirmar(Documento.objects.get(id=self.client.post(f"/api/v1/documentos/{recibo.id}/generar-factura/").json()["id"]))
        self.anular(f, False)
        r = self.client.post(f"/api/v1/documentos/{recibo.id}/generar-factura/")
        self.assertEqual(r.status_code, 201)
        self.assertNotEqual(r.json()["id"], f.id)
