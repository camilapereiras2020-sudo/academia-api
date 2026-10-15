from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from modules.alumnos.models import Alumno
from modules.pagadores.models import Pagador

User = get_user_model()


class AlumnoSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        pagador = Pagador.objects.create(
            academia=self.user, nombre="María Pérez", nif="12345678Z", telefono="611 22 33 44",
        )
        self.nino = Alumno.objects.create(academia=self.user, nombre="Lucas Gómez", pagador=pagador)
        self.adulto = Alumno.objects.create(
            academia=self.user, nombre="Ana Ruiz", telefono="699 888 777", dni="X1234567L",
        )

    def buscar(self, q):
        resp = self.client.get("/api/v1/alumnos/", {"search": q})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        rows = data["results"] if isinstance(data, dict) else data
        return {r["id"] for r in rows}

    def test_por_nombre_de_alumno(self):
        self.assertEqual(self.buscar("lucas"), {self.nino.id})

    def test_por_nombre_de_pagador(self):
        self.assertEqual(self.buscar("pérez"), {self.nino.id})

    def test_por_telefono_ignorando_espacios(self):
        self.assertEqual(self.buscar("699888"), {self.adulto.id})
        self.assertEqual(self.buscar("611 223"), {self.nino.id})

    def test_por_dni_y_nif(self):
        self.assertEqual(self.buscar("x1234567"), {self.adulto.id})
        self.assertEqual(self.buscar("12345678z"), {self.nino.id})
