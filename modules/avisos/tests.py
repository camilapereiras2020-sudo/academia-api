from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Aviso

User = get_user_model()


class AvisoViewSetTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="cami", email="cami@example.com", password="x")
        self.candela = User.objects.create_user(
            username="candela", email="candela@example.com", password="x",
            role="co_manager", academia_owner=self.owner,
        )
        self.sofia = User.objects.create_user(
            username="sofia", email="sofia@example.com", password="x",
            role="reception", academia_owner=self.owner,
        )
        other_owner = User.objects.create_user(username="other", email="other@example.com", password="x")
        self.other_staff = User.objects.create_user(
            username="ajeno", email="ajeno@example.com", password="x",
            role="reception", academia_owner=other_owner,
        )
        self.client = APIClient()

    def test_equipo_lists_every_account_in_the_tenant(self):
        self.client.force_authenticate(self.candela)
        resp = self.client.get("/api/v1/avisos/equipo/")
        self.assertEqual(resp.status_code, 200)
        usernames = {u["username"] for u in resp.json()}
        self.assertEqual(usernames, {"cami", "candela", "sofia"})

    def test_anyone_in_the_tenant_can_send_a_note_to_a_teammate(self):
        self.client.force_authenticate(self.candela)
        resp = self.client.post("/api/v1/avisos/", {"titulo": "Avisale a Sofia", "para": self.sofia.id})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["creado_por_nombre"], "candela")
        self.assertEqual(resp.json()["para_nombre"], "sofia")

    def test_cannot_address_a_note_to_someone_outside_the_tenant(self):
        self.client.force_authenticate(self.candela)
        resp = self.client.post("/api/v1/avisos/", {"titulo": "Hola", "para": self.other_staff.id})
        self.assertEqual(resp.status_code, 400)

    def test_para_mi_only_returns_unread_notes_addressed_to_me(self):
        Aviso.objects.create(academia=self.owner, creado_por=self.owner, para=self.sofia, titulo="Para Sofia")
        Aviso.objects.create(academia=self.owner, creado_por=self.owner, para=self.candela, titulo="Para Candela")
        Aviso.objects.create(academia=self.owner, creado_por=self.owner, para=self.sofia, titulo="Ya leida", hecha=True)

        self.client.force_authenticate(self.sofia)
        resp = self.client.get("/api/v1/avisos/?para_mi=1")
        self.assertEqual(resp.status_code, 200)
        titulos = [a["titulo"] for a in resp.json()]
        self.assertEqual(titulos, ["Para Sofia"])

    def test_calendar_range_shows_tasks_from_the_whole_team_not_just_mine(self):
        Aviso.objects.create(academia=self.owner, creado_por=self.owner, para=self.candela, titulo="Tarea Candela", fecha="2026-09-15")
        Aviso.objects.create(academia=self.owner, creado_por=self.candela, para=None, titulo="Tarea sin asignar", fecha="2026-09-16")
        Aviso.objects.create(academia=self.owner, creado_por=self.owner, para=self.candela, titulo="Nota sin fecha")

        self.client.force_authenticate(self.sofia)
        resp = self.client.get("/api/v1/avisos/?desde=2026-09-01&hasta=2026-09-30")
        self.assertEqual(resp.status_code, 200)
        titulos = {a["titulo"] for a in resp.json()}
        self.assertEqual(titulos, {"Tarea Candela", "Tarea sin asignar"})

    def test_recipient_can_mark_a_note_as_read_but_a_bystander_cannot_edit_it(self):
        aviso = Aviso.objects.create(academia=self.owner, creado_por=self.owner, para=self.sofia, titulo="Para Sofia")

        # Candela is neither the sender nor the recipient of this note, and
        # it has no fecha (so it's not on the shared calendar either) — her
        # queryset doesn't even include it, so it 404s rather than 403s.
        self.client.force_authenticate(self.candela)
        resp = self.client.patch(f"/api/v1/avisos/{aviso.id}/", {"hecha": True})
        self.assertEqual(resp.status_code, 404)

        self.client.force_authenticate(self.sofia)
        resp = self.client.patch(f"/api/v1/avisos/{aviso.id}/", {"hecha": True})
        self.assertEqual(resp.status_code, 200)
        aviso.refresh_from_db()
        self.assertTrue(aviso.hecha)

    def test_bystander_can_see_a_shared_calendar_task_but_not_edit_it(self):
        tarea = Aviso.objects.create(
            academia=self.owner, creado_por=self.owner, para=self.candela,
            titulo="Tarea Candela", fecha="2026-09-15",
        )
        # Sofia isn't the creator or the assignee, but a task (fecha set) is
        # on the shared calendar, so she can see it — just not touch it.
        self.client.force_authenticate(self.sofia)
        get_resp = self.client.get(f"/api/v1/avisos/{tarea.id}/")
        self.assertEqual(get_resp.status_code, 200)
        patch_resp = self.client.patch(f"/api/v1/avisos/{tarea.id}/", {"hecha": True})
        self.assertEqual(patch_resp.status_code, 403)

    def test_cannot_see_avisos_from_another_academia(self):
        other_owner = self.other_staff.academia_owner
        Aviso.objects.create(academia=other_owner, creado_por=other_owner, para=None, titulo="No es mío", fecha="2026-09-15")

        self.client.force_authenticate(self.owner)
        resp = self.client.get("/api/v1/avisos/?desde=2026-09-01&hasta=2026-09-30")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])
