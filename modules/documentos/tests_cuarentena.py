"""Tests del Modo cuarentena. Efectos externos (Drive, Sheets) mockeados."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from modules.alumnos.models import Alumno
from modules.documentos.models import Documento, Emisor
from modules.grupos.models import Grupo
from modules.pagadores.models import Pagador
from modules.pagos.models import Pago

User = get_user_model()


@patch("modules.documentos.sheets_log.log_emision")
@patch("modules.documentos.cuarentena.upload_to_drive", return_value="DRIVE")
class CuarentenaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", email="o@example.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cami = Emisor.objects.create(
            academia=self.user, slug="camiandco", nombre="Cami&Co", autonoma="C", nif="X1",
            direccion="X", ciudad="X", factura_prefix="CC", recibo_prefix="RE",
        )
        self.rangers = Emisor.objects.create(
            academia=self.user, slug="rangers", nombre="Rangers", autonoma="R", nif="X2",
            direccion="X", ciudad="X", factura_prefix="RA", recibo_prefix="RR",
        )
        self.pagador = Pagador.objects.create(academia=self.user, nombre="Mamá")
        self.grupo = Grupo.objects.create(
            academia=self.user, marca="cami_and_co", nombre="G", nivel="A1", tarifa=80,
        )

    def pago(self, nombre="Hijo", metodo="transferencia", emisor=None, pagador=True):
        al = Alumno.objects.create(
            academia=self.user, nombre=nombre, marca="cami_and_co",
            pagador=self.pagador if pagador else None,
        )
        al.grupos.add(self.grupo)
        return Pago.objects.create(
            academia=self.user, marca="cami_and_co", emisor=emisor or self.cami,
            pagador=self.pagador if pagador else None, alumno=al, grupo=self.grupo,
            periodo="2026-10", fecha="2026-10-01", mensualidad=80, descuento=0, extras=[],
            total=80, metodo=metodo, estado="pagado", estado_carga="completo",
        )

    def activar(self, on=True):
        self.user.modo_cuarentena = on
        self.user.save()

    def generar(self, pago):
        return self.client.post("/api/v1/documentos/generar/", {"pago_id": pago.id}, format="json")

    def confirmar(self, ids):
        return self.client.post("/api/v1/documentos/confirmar/", {"ids": ids}, format="json")

    # ── nacimiento ──────────────────────────────────────────────────────
    def test_modo_activo_nace_en_cuarentena_sin_numero_ni_drive(self, m_up, m_log):
        self.activar()
        r = self.generar(self.pago("A"))
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertEqual((d["estado"], d["num_doc"], d["provisional"]), ("cuarentena", "", True))
        m_up.assert_not_called()
        m_log.assert_not_called()
        self.cami.refresh_from_db()
        self.assertEqual(self.cami.factura_counter, 0)
        # el PDF provisional se renderiza al vuelo
        pdf = self.client.get(d["download_url"].replace("/api/v1", "/api/v1"))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_generar_es_idempotente_en_cuarentena(self, m_up, m_log):
        self.activar()
        p = self.pago("A")
        a, b = self.generar(p).json(), self.generar(p).json()
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(Documento.objects.count(), 1)

    def test_modo_apagado_comportamiento_de_hoy(self, m_up, m_log):
        with patch("modules.documentos.invoice_service.upload_to_drive", return_value="D"):
            r = self.generar(self.pago("A"))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["estado"], "emitida")
        self.assertEqual(r.json()["num_doc"], "CC1-26")

    def test_documentos_previos_no_entran_en_cuarentena(self, m_up, m_log):
        p = self.pago("A")
        with patch("modules.documentos.invoice_service.upload_to_drive", return_value="D"):
            emitido = self.generar(p).json()
        self.activar()
        again = self.generar(p)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["id"], emitido["id"])
        self.assertEqual(again.json()["estado"], "emitida")

    # ── eliminar / enviar ───────────────────────────────────────────────
    def test_eliminar_cuarentena_ok_y_confirmado_no(self, m_up, m_log):
        self.activar()
        d = self.generar(self.pago("A")).json()
        self.assertEqual(self.client.delete(f"/api/v1/documentos/{d['id']}/").status_code, 204)
        d2 = self.generar(self.pago("B")).json()
        self.assertEqual(self.confirmar([d2["id"]]).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/v1/documentos/{d2['id']}/").status_code, 409)

    def test_no_se_puede_enviar_en_cuarentena(self, m_up, m_log):
        self.activar()
        d = self.generar(self.pago("A")).json()
        r = self.client.post(f"/api/v1/documentos/{d['id']}/enviar/")
        self.assertEqual(r.status_code, 409)

    # ── la prueba pedida ────────────────────────────────────────────────
    def test_tres_borrar_el_del_medio_confirmar_dos_sin_hueco(self, m_up, m_log):
        self.activar()
        ids = [self.generar(self.pago(n)).json()["id"] for n in ("A", "B", "C")]
        self.assertEqual(self.client.delete(f"/api/v1/documentos/{ids[1]}/").status_code, 204)
        r = self.confirmar([ids[2], ids[0]])  # orden de petición irrelevante
        self.assertEqual(r.status_code, 200, r.content)
        nums = {Documento.objects.get(pk=i).num_doc for i in (ids[0], ids[2])}
        self.assertEqual(Documento.objects.get(pk=ids[0]).num_doc, "CC1-26")
        self.assertEqual(Documento.objects.get(pk=ids[2]).num_doc, "CC2-26")
        self.assertEqual(nums, {"CC1-26", "CC2-26"})
        self.cami.refresh_from_db()
        self.assertEqual(self.cami.factura_counter, 2)

    def test_reglas_de_numeracion_por_metodo_y_emisor(self, m_up, m_log):
        self.activar()
        ids = [
            self.generar(self.pago("A", "bizum")).json()["id"],
            self.generar(self.pago("B", "efectivo")).json()["id"],
            self.generar(self.pago("C", "domiciliacion")).json()["id"],
            self.generar(self.pago("D", "tarjeta", emisor=self.rangers)).json()["id"],
        ]
        self.assertEqual(self.confirmar(ids).status_code, 200)
        got = [Documento.objects.get(pk=i) for i in ids]
        self.assertEqual([(d.tipo, d.num_doc) for d in got], [
            ("factura", "CC1-26"), ("recibo", "RE1-26"), ("recibo", "RE2-26"), ("factura", "RA1-26"),
        ])
        for d in got:
            self.assertEqual((d.estado, d.pago.num_doc), ("emitida", d.num_doc))
            self.assertTrue(d.pdf_data)

    def test_confirmar_dos_veces_no_renumera(self, m_up, m_log):
        self.activar()
        d = self.generar(self.pago("A")).json()
        self.assertEqual(self.confirmar([d["id"]]).status_code, 200)
        self.assertEqual(self.confirmar([d["id"]]).status_code, 409)
        self.cami.refresh_from_db()
        self.assertEqual(self.cami.factura_counter, 1)

    def test_confirmar_falla_todo_o_nada_sin_huecos(self, m_up, m_log):
        self.activar()
        a = self.generar(self.pago("A")).json()["id"]
        b = self.generar(self.pago("B")).json()["id"]
        with patch("modules.documentos.cuarentena.render_documento_pdf", side_effect=[(b"%PDF", __import__("datetime").date.today(), self.cami), ValueError("boom")]):
            self.assertEqual(self.confirmar([a, b]).status_code, 400)
        self.cami.refresh_from_db()
        self.assertEqual(self.cami.factura_counter, 0)
        self.assertEqual(Documento.objects.filter(estado="cuarentena").count(), 2)
        self.assertEqual(self.confirmar([a, b]).status_code, 200)
        self.assertEqual(
            sorted(Documento.objects.values_list("num_doc", flat=True)), ["CC1-26", "CC2-26"]
        )

    def test_reception_no_confirma_pero_si_elimina_cuarentena(self, m_up, m_log):
        self.activar()
        d = self.generar(self.pago("A")).json()
        rec = User.objects.create_user(
            username="rec", email="r@example.com", password="x", role="reception", academia_owner=self.user,
        )
        c = APIClient(); c.force_authenticate(rec)
        self.assertEqual(c.post("/api/v1/documentos/confirmar/", {"ids": [d["id"]]}, format="json").status_code, 403)
        self.assertEqual(c.delete(f"/api/v1/documentos/{d['id']}/").status_code, 204)

    # ── juntar (Bono Familia) ───────────────────────────────────────────
    def test_juntar_mismo_pagador_y_confirmar_un_solo_numero(self, m_up, m_log):
        self.activar()
        ids = [self.generar(self.pago(n)).json()["id"] for n in ("A", "B")]
        r = self.client.post("/api/v1/documentos/juntar/", {"ids": ids}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()["pagos_adicionales"]), 1)
        self.assertEqual(Documento.objects.count(), 1)
        c = self.confirmar([r.json()["id"]])
        self.assertEqual(c.status_code, 200, c.content)
        self.assertEqual(c.json()[0]["num_doc"], "CC1-26")

    def test_juntar_distinto_pagador_falla(self, m_up, m_log):
        self.activar()
        otro = Pagador.objects.create(academia=self.user, nombre="Otro")
        pa = self.pago("A")
        pb = self.pago("B")
        pb.pagador = otro; pb.save()
        ids = [self.generar(pa).json()["id"], self.generar(pb).json()["id"]]
        r = self.client.post("/api/v1/documentos/juntar/", {"ids": ids}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Documento.objects.count(), 2)

    def test_generar_combinado_en_cuarentena(self, m_up, m_log):
        self.activar()
        a, b = self.pago("A"), self.pago("B")
        r = self.client.post("/api/v1/documentos/generar-combinado/", {"pago_ids": [a.id, b.id]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()["estado"], r.json()["num_doc"]), ("cuarentena", ""))

    # ── filtro + anular ─────────────────────────────────────────────────
    def test_filtro_estado_y_anular_solo_confirmados(self, m_up, m_log):
        self.activar()
        a = self.generar(self.pago("A")).json()["id"]
        lst = self.client.get("/api/v1/documentos/?estado=cuarentena").json()
        rows = lst["results"] if isinstance(lst, dict) else lst
        self.assertEqual([x["id"] for x in rows], [a])
        r = self.client.post(f"/api/v1/documentos/{a}/anular/", {"motivo_anulacion": "x"}, format="json")
        self.assertEqual(r.status_code, 400)  # en cuarentena se elimina, no se anula
