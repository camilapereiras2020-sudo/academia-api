from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Profesor
from modules.grupos.models import Grupo

User = get_user_model()


class ProfesorViewSetTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", email="owner@example.com", password="x")
        self.reception = User.objects.create_user(
            username="reception", email="reception@example.com", password="x", role="reception", academia_owner=self.owner
        )
        self.cami = Profesor.objects.create(academia=self.owner, nombre="Cami", orden=0)
        self.cande = Profesor.objects.create(academia=self.owner, nombre="Cande", orden=1)
        self.suplente = Profesor.objects.create(academia=self.owner, nombre="Suplente", es_suplente=True, orden=2)

        other_owner = User.objects.create_user(username="other", email="other@example.com", password="x")
        Profesor.objects.create(academia=other_owner, nombre="Otro Profesor")

        self.client = APIClient()

    def test_owner_lists_only_own_profesores_ordered(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.get("/api/v1/profesores/")
        self.assertEqual(resp.status_code, 200)
        nombres = [p["nombre"] for p in resp.json()]
        self.assertEqual(nombres, ["Cami", "Cande", "Suplente"])

    def test_reception_can_read_but_not_create(self):
        self.client.force_authenticate(self.reception)
        get_resp = self.client.get("/api/v1/profesores/")
        self.assertEqual(get_resp.status_code, 200)
        post_resp = self.client.post("/api/v1/profesores/", {"nombre": "Nuevo"})
        self.assertEqual(post_resp.status_code, 403)

    def test_cannot_create_duplicate_nombre_for_same_academia(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post("/api/v1/profesores/", {"nombre": "Cami"})
        self.assertEqual(resp.status_code, 400)

    def test_grupo_can_be_assigned_a_profesor_and_exposes_profesor_nombre(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post("/api/v1/grupos/", {
            "nombre": "Cambridge FCE Martes", "marca": "cami_and_co", "profesor": self.cami.id,
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["profesor_nombre"], "Cami")

    def test_grupo_rejects_profesor_from_another_academia(self):
        other_owner = User.objects.get(email="other@example.com")
        other_profesor = Profesor.objects.get(academia=other_owner)
        self.client.force_authenticate(self.owner)
        resp = self.client.post("/api/v1/grupos/", {
            "nombre": "Cambridge FCE Martes", "marca": "cami_and_co", "profesor": other_profesor.id,
        })
        self.assertEqual(resp.status_code, 400)

    def test_deleting_profesor_sets_grupo_profesor_to_null_not_delete_grupo(self):
        grupo = Grupo.objects.create(academia=self.owner, nombre="Infantil Miercoles", profesor=self.cande)
        self.cande.delete()
        grupo.refresh_from_db()
        self.assertIsNone(grupo.profesor)
