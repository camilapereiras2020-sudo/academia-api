from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from modules.alumnos.models import Alumno
from modules.pagos.models import Pago

from .models import Pagador

User = get_user_model()


class PagadorDeleteTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="o", email="o@example.com", password="x", role="owner")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def _delete(self, pagador):
        return self.client.delete(f"/api/v1/pagadores/{pagador.id}/")

    def test_borra_un_pagador_sin_alumnos_ni_pagos(self):
        p = Pagador.objects.create(academia=self.owner, nombre="Duplicado por typo")
        resp = self._delete(p)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Pagador.objects.filter(id=p.id).exists())

    def test_no_borra_si_tiene_alumnos_y_los_deja_asignados(self):
        p = Pagador.objects.create(academia=self.owner, nombre="Familia X")
        a = Alumno.objects.create(academia=self.owner, nombre="Hijo", pagador=p)
        resp = self._delete(p)
        self.assertEqual(resp.status_code, 409)
        self.assertIn("Hijo", resp.json()["error"])
        a.refresh_from_db()
        self.assertEqual(a.pagador_id, p.id)

    def test_no_borra_si_tiene_pagos(self):
        p = Pagador.objects.create(academia=self.owner, nombre="Familia Y")
        Pago.objects.create(academia=self.owner, pagador=p, periodo="2026-10", total=Decimal("50"), metodo="bizum")
        resp = self._delete(p)
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(Pagador.objects.filter(id=p.id).exists())

    def test_no_se_puede_borrar_un_pagador_de_otra_academia(self):
        otro = User.objects.create_user(username="x", email="x@example.com", password="x", role="owner")
        p = Pagador.objects.create(academia=otro, nombre="Ajeno")
        self.assertEqual(self._delete(p).status_code, 404)
        self.assertTrue(Pagador.objects.filter(id=p.id).exists())
