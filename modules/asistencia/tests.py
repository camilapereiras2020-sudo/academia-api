from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from modules.alumnos.models import Alumno
from modules.asistencia.models import RegistroAsistencia, Sesion
from modules.grupos.models import Grupo

User = get_user_model()


class InvitadoRecuperacionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="o", email="o@example.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.grupo = Grupo.objects.create(academia=self.user, marca="cami_and_co", nombre="G1", nivel="A1", tarifa=60)
        self.otro = Grupo.objects.create(academia=self.user, marca="cami_and_co", nombre="G2", nivel="A1", tarifa=60)
        self.propio = Alumno.objects.create(academia=self.user, nombre="Propio", marca="cami_and_co")
        self.propio.grupos.add(self.grupo)
        self.visita = Alumno.objects.create(academia=self.user, nombre="Visita", marca="cami_and_co")
        self.visita.grupos.add(self.otro)

    def marcar(self, alumno, estado, **extra):
        return self.client.post(
            "/api/v1/asistencia/marcar/",
            {"grupo": self.grupo.id, "fecha": "2026-10-19", "alumno": alumno.id, "estado": estado, **extra},
            format="json",
        )

    def test_recuperacion_de_alumno_de_otro_grupo_se_marca_como_invitado(self):
        r = self.marcar(self.visita, "makeup", nota="recupera del martes")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["estado"], r.json()["es_invitado"]), ("makeup", True))

    def test_alumno_de_la_clase_no_es_invitado(self):
        self.assertFalse(self.marcar(self.propio, "present").json()["es_invitado"])

    def test_quitar_invitado_lo_borra_pero_no_a_un_alumno_de_la_clase(self):
        self.marcar(self.visita, "guest")
        self.marcar(self.propio, "present")
        datos = lambda a: {"grupo": self.grupo.id, "fecha": "2026-10-19", "alumno": a.id}
        self.assertEqual(self.client.post("/api/v1/asistencia/quitar/", datos(self.visita), format="json").status_code, 204)
        self.assertFalse(RegistroAsistencia.objects.filter(alumno=self.visita).exists())
        self.assertEqual(self.client.post("/api/v1/asistencia/quitar/", datos(self.propio), format="json").status_code, 400)
        self.assertTrue(RegistroAsistencia.objects.filter(alumno=self.propio).exists())

    def test_quitar_registro_inexistente_da_404(self):
        r = self.client.post("/api/v1/asistencia/quitar/", {"grupo": self.grupo.id, "fecha": "2026-10-19", "alumno": self.visita.id}, format="json")
        self.assertEqual(r.status_code, 404)
