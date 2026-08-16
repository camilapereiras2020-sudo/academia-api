from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Nivel

User = get_user_model()


class NivelViewSetTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", email="owner@example.com", password="x")
        self.reception = User.objects.create_user(
            username="reception", email="reception@example.com", password="x",
            role="reception", academia_owner=self.owner,
        )
        self.kids_a = Nivel.objects.create(academia=self.owner, categoria="kids", nombre="Pre-A1 Starters", orden=0)
        self.kids_b = Nivel.objects.create(academia=self.owner, categoria="kids", nombre="A1 Movers", orden=1)
        self.adults_a = Nivel.objects.create(academia=self.owner, categoria="adults", nombre="A1 Beginner", orden=0)
        # belongs to a different academia entirely — must never leak into owner's list
        other_owner = User.objects.create_user(username="other", email="other@example.com", password="x")
        Nivel.objects.create(academia=other_owner, categoria="kids", nombre="Other Academy Level", orden=0)

        self.client = APIClient()

    def test_owner_lists_only_own_niveles_ordered_by_categoria_then_orden(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.get("/api/v1/niveles/")
        self.assertEqual(resp.status_code, 200)
        nombres = [n["nombre"] for n in resp.json()]
        self.assertEqual(nombres, ["A1 Beginner", "Pre-A1 Starters", "A1 Movers"])

    def test_filter_by_categoria(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.get("/api/v1/niveles/?categoria=kids")
        self.assertEqual(resp.status_code, 200)
        nombres = {n["nombre"] for n in resp.json()}
        self.assertEqual(nombres, {"Pre-A1 Starters", "A1 Movers"})

    def test_filter_by_activo(self):
        self.kids_b.activo = False
        self.kids_b.save(update_fields=["activo"])
        self.client.force_authenticate(self.owner)
        resp = self.client.get("/api/v1/niveles/?activo=true")
        nombres = {n["nombre"] for n in resp.json()}
        self.assertNotIn("A1 Movers", nombres)

    def test_reception_can_read_but_not_create(self):
        self.client.force_authenticate(self.reception)
        get_resp = self.client.get("/api/v1/niveles/")
        self.assertEqual(get_resp.status_code, 200)

        post_resp = self.client.post("/api/v1/niveles/", {"nombre": "New", "categoria": "kids"})
        self.assertEqual(post_resp.status_code, 403)

    def test_owner_can_create_edit_reorder_and_deactivate(self):
        self.client.force_authenticate(self.owner)

        create_resp = self.client.post(
            "/api/v1/niveles/", {"nombre": "A2 Flyers", "categoria": "kids", "orden": 2}
        )
        self.assertEqual(create_resp.status_code, 201, create_resp.content)
        new_id = create_resp.json()["id"]
        self.assertEqual(Nivel.objects.get(pk=new_id).academia_id, self.owner.id)

        rename_resp = self.client.patch(f"/api/v1/niveles/{self.kids_a.id}/", {"nombre": "Starters (renamed)"})
        self.assertEqual(rename_resp.status_code, 200)
        self.kids_a.refresh_from_db()
        self.assertEqual(self.kids_a.nombre, "Starters (renamed)")

        reorder_resp = self.client.patch(f"/api/v1/niveles/{self.kids_a.id}/", {"orden": 5})
        self.assertEqual(reorder_resp.status_code, 200)
        self.kids_a.refresh_from_db()
        self.assertEqual(self.kids_a.orden, 5)

        deactivate_resp = self.client.patch(f"/api/v1/niveles/{self.kids_b.id}/", {"activo": False})
        self.assertEqual(deactivate_resp.status_code, 200)
        self.kids_b.refresh_from_db()
        self.assertFalse(self.kids_b.activo)

    def test_cannot_create_duplicate_nombre_within_same_categoria(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            "/api/v1/niveles/", {"nombre": "Pre-A1 Starters", "categoria": "kids"}
        )
        self.assertEqual(resp.status_code, 400)
