from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from modules.alumnos.models import Alumno, Inscripcion
from modules.grupos.models import Grupo
from modules.pagadores.models import Pagador
from modules.pagos.models import Pago
from modules.profesores.models import Profesor
from modules.tarifas.management.commands.reparto_cobros import SIN_ASIGNAR, calcular_reparto

User = get_user_model()


class RepartoCobrosTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="o", email="o@example.com", password="x", role="owner")
        self.cande = Profesor.objects.create(academia=self.owner, nombre="Cande", codigo="P1")
        self.cami = Profesor.objects.create(academia=self.owner, nombre="Cami", codigo="P2")
        self.g_cande = Grupo.objects.create(academia=self.owner, nombre="G Cande", profesor=self.cande)
        self.g_cami = Grupo.objects.create(academia=self.owner, nombre="G Cami", profesor=self.cami)
        self.pagador = Pagador.objects.create(academia=self.owner, nombre="Familia X")

    def _pago(self, nombre, grupo, total, estado="pagado", periodo="2026-10", grupo_en_pago=True):
        alumno = Alumno.objects.create(academia=self.owner, nombre=nombre, pagador=self.pagador)
        if grupo:
            Inscripcion.objects.create(alumno=alumno, grupo=grupo)
        return Pago.objects.create(
            academia=self.owner, pagador=self.pagador, alumno=alumno,
            grupo=grupo if grupo_en_pago else None,
            periodo=periodo, total=Decimal(total), metodo="bizum", estado=estado,
        )

    def test_reparte_dos_hermanos_entre_cande_y_cami(self):
        self._pago("Hijo1", self.g_cande, "50")
        self._pago("Hijo2", self.g_cami, "45")
        por_pagador, totales = calcular_reparto(self.owner, "2026-10")
        self.assertEqual(len(por_pagador["Familia X"]), 2)
        self.assertEqual(totales, {"Cande": Decimal("50"), "Cami": Decimal("45")})

    def test_usa_el_grupo_del_alumno_si_el_pago_no_tiene_grupo(self):
        self._pago("Hijo1", self.g_cami, "45", grupo_en_pago=False)
        _, totales = calcular_reparto(self.owner, "2026-10")
        self.assertEqual(totales, {"Cami": Decimal("45")})

    def test_sin_grupo_queda_sin_asignar_y_no_se_adivina(self):
        self._pago("Hijo1", None, "30")
        _, totales = calcular_reparto(self.owner, "2026-10")
        self.assertEqual(totales, {SIN_ASIGNAR: Decimal("30")})

    def test_alumno_en_grupos_de_ambas_profesoras_queda_sin_asignar(self):
        p = self._pago("Hijo1", self.g_cande, "60", grupo_en_pago=False)
        Inscripcion.objects.create(alumno=p.alumno, grupo=self.g_cami)
        _, totales = calcular_reparto(self.owner, "2026-10")
        self.assertEqual(totales, {SIN_ASIGNAR: Decimal("60")})

    def test_solo_pagados_y_solo_el_periodo_pedido(self):
        self._pago("A", self.g_cami, "45")
        self._pago("B", self.g_cami, "45", estado="pendiente")
        self._pago("C", self.g_cami, "45", periodo="2026-09")
        _, totales = calcular_reparto(self.owner, "2026-10")
        self.assertEqual(totales, {"Cami": Decimal("45")})
        _, totales = calcular_reparto(self.owner, "2026-10", solo_pagados=False)
        self.assertEqual(totales, {"Cami": Decimal("90")})
