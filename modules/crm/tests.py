"""Reception's access to CRM leads/interacciones — she fields most of these
calls, so she needs to log and follow up on them (unlike before, when
NotReception blocked the whole module). The one thing still reserved is
convertir_alumno, since it creates a real Alumno + Pago (an enrollment
decision, same line AlumnoViewSet.perform_create already draws)."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from modules.crm.models import Lead
from modules.grupos.models import Grupo

User = get_user_model()


class ReceptionCrmAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", email="owner@example.com", password="x")
        self.reception = User.objects.create_user(
            username="reception", email="reception@example.com", password="x",
            role="reception", academia_owner=self.owner,
        )

        self.client = APIClient()

        self.lead = Lead.objects.create(
            academia=self.owner, marca="rangers_academy",
            nombre_contacto="Mamá Pérez", nombre_alumno="Hijo Pérez",
            telefono="600111222", origen="telefono",
        )

    def _as(self, user):
        self.client.force_authenticate(user)

    @patch("modules.crm.views.append_contacto_row")
    def test_reception_can_list_and_create_leads(self, mock_append):
        self._as(self.reception)
        resp = self.client.get("/api/v1/leads/")
        self.assertEqual(resp.status_code, 200, resp.content)

        resp = self.client.post("/api/v1/leads/", {
            "marca": "cami_and_co", "nombre_contacto": "Otra Madre",
            "nombre_alumno": "Otro Hijo", "telefono": "600333444", "origen": "telefono",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_reception_can_update_lead_and_change_etapa(self):
        self._as(self.reception)
        resp = self.client.patch(f"/api/v1/leads/{self.lead.id}/", {"notas": "Llamó, pide info de horarios."}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)

        resp = self.client.post(f"/api/v1/leads/{self.lead.id}/cambiar-etapa/", {"etapa": "en_conversacion"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_reception_can_log_interaccion(self):
        self._as(self.reception)
        resp = self.client.post("/api/v1/interacciones/", {
            "lead": self.lead.id, "tipo": "llamada", "resumen": "Preguntó por el horario de tarde.",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.last_contacted_at)

    def test_reception_blocked_from_convertir_alumno(self):
        grupo = Grupo.objects.create(
            academia=self.owner, marca="rangers_academy", nombre="Rangers Kids", nivel="A1", tarifa=80,
        )
        self._as(self.reception)
        resp = self.client.post(f"/api/v1/leads/{self.lead.id}/convertir-alumno/", {
            "grupo_id": grupo.id, "mensualidad": "80", "fecha_inicio": "2026-09-01",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_owner_convertir_alumno_unaffected(self):
        grupo = Grupo.objects.create(
            academia=self.owner, marca="rangers_academy", nombre="Rangers Kids", nivel="A1", tarifa=80,
        )
        self._as(self.owner)
        resp = self.client.post(f"/api/v1/leads/{self.lead.id}/convertir-alumno/", {
            "grupo_id": grupo.id, "mensualidad": "80", "fecha_inicio": "2026-09-01",
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
