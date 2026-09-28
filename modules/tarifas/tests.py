"""Tarifa oficial Rangers Academy 2026/2027 — lo que se entrega a las familias.

Fuente: la tarifa en PDF para familias (90 min: "Tarifa-Rangers-26-27.pdf")
y la tarifa de 1 hora acordada con dirección. Si una cifra de aquí cambia,
tiene que cambiar primero en el PDF que reciben los clientes.

Reglas que fijan estos tests:
- Clases Grupo: tabla fija por días/semana. 90 min solo existe de 1 a 3 días.
- Bono Familia: tabla fija (sin fórmula), para 2 hermanos que van los mismos
  días y la misma duración; se reparte a partes iguales. Cualquier otro caso
  (3-4 hermanos, perfiles distintos) no está en la tarifa: precio manual.
- Privada 30 €/h; privada profesional o especialización 35 €/h (sin cálculo
  automático: se carga a mano).
- Matrícula 20 €.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from modules.alumnos.models import Alumno, Inscripcion
from modules.grupos.models import Grupo
from modules.pagadores.models import Pagador
from modules.tarifas import pricing

User = get_user_model()

TARIFA_GRUPO = {
    60: {1: 50, 2: 95, 3: 145, 4: 185, 5: 230},
    90: {1: 75, 2: 137, 3: 200},
}
TARIFA_BONO_FAMILIA = {
    60: {1: 95, 2: 180, 3: 275, 4: 350, 5: 435},
    90: {1: 130, 2: 260, 3: 375},
}


class TarifaOficialTests(SimpleTestCase):
    def test_clases_grupo_coinciden_con_la_tarifa(self):
        for duracion, filas in TARIFA_GRUPO.items():
            for dias, precio in filas.items():
                with self.subTest(duracion=duracion, dias=dias):
                    self.assertEqual(pricing.precio_clase_grupo(dias, duracion), precio)

    def test_bono_familia_coincide_con_la_tarifa(self):
        for duracion, filas in TARIFA_BONO_FAMILIA.items():
            for dias, precio in filas.items():
                with self.subTest(duracion=duracion, dias=dias):
                    self.assertEqual(pricing.precio_bono_familia(dias, duracion), precio)

    def test_no_hay_precios_fuera_de_la_tarifa(self):
        # 90 min con 4 o 5 días no existe en la tarifa.
        for dias in (4, 5):
            self.assertIsNone(pricing.precio_clase_grupo(dias, 90))
            self.assertIsNone(pricing.precio_bono_familia(dias, 90))
        # No existen clases de 2 horas.
        self.assertIsNone(pricing.precio_clase_grupo(1, 120))
        self.assertIsNone(pricing.precio_bono_familia(1, 120))
        for dias in (0, 6):
            self.assertIsNone(pricing.precio_clase_grupo(dias, 60))

    def test_tablas_completas_sin_filas_de_mas(self):
        self.assertEqual(pricing.CLASES_GRUPO, TARIFA_GRUPO)
        self.assertEqual(pricing.BONO_FAMILIA, TARIFA_BONO_FAMILIA)

    def test_privadas_y_matricula(self):
        self.assertEqual(pricing.PRECIO_CLASE_PRIVADA_HORA, 30)
        self.assertEqual(pricing.PRECIO_CLASE_PRIVADA_PROFESIONAL_HORA, 35)
        self.assertEqual(pricing.MATRICULA, 20)


class CuotaAlumnoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="owner@test.local", username="owner", password="x")
        self.pagador = Pagador.objects.create(academia=self.user, nombre="Familia Test")

    def grupo(self, dias, ini="17:00", fin="18:00"):
        return Grupo.objects.create(
            academia=self.user, nombre=f"G{dias}-{ini}-{fin}",
            horarios=[{"dia": d, "ini": ini, "fin": fin} for d in range(dias)],
        )

    def alumno(self, nombre, grupo, pagador=None, **extra):
        a = Alumno.objects.create(academia=self.user, nombre=nombre, pagador=pagador, **extra)
        if grupo is not None:
            Inscripcion.objects.create(alumno=a, grupo=grupo)
        return a

    def test_clase_grupo_individual_60_y_90(self):
        a = self.alumno("Uno", self.grupo(2))
        r = pricing.calcular_cuota_alumno(a)
        self.assertEqual((r["tipo"], r["cuota"]), ("clase_grupo", 95.0))

        b = self.alumno("Dos", self.grupo(3, "17:00", "18:30"))
        r = pricing.calcular_cuota_alumno(b)
        self.assertEqual((r["tipo"], r["cuota"]), ("clase_grupo", 200.0))

    def test_90_min_cuatro_dias_no_esta_en_la_tarifa(self):
        a = self.alumno("Cuatro", self.grupo(4, "17:00", "18:30"))
        r = pricing.calcular_cuota_alumno(a)
        self.assertEqual(r["tipo"], "sin_tabla")
        self.assertIsNone(r["cuota"])

    def test_bono_familia_dos_hermanos_mismo_perfil_tabla_fija(self):
        g = self.grupo(2)
        a = self.alumno("Hermano A", g, self.pagador)
        b = self.alumno("Hermano B", g, self.pagador)
        for x in (a, b):
            r = pricing.calcular_cuota_alumno(x)
            self.assertEqual(r["tipo"], "bono_familia")
            self.assertEqual(r["total_bono"], 180.0)
            self.assertEqual(r["cuota"], 90.0)

    def test_bono_familia_90_min(self):
        g = self.grupo(3, "17:00", "18:30")
        a = self.alumno("Hermano A", g, self.pagador)
        self.alumno("Hermano B", g, self.pagador)
        r = pricing.calcular_cuota_alumno(a)
        self.assertEqual((r["tipo"], r["total_bono"], r["cuota"]), ("bono_familia", 375.0, 187.5))

    def test_bono_familia_importe_impar_cuadra_al_centimo(self):
        g = self.grupo(1)  # 95 € entre 2
        a = self.alumno("Hermano A", g, self.pagador)
        b = self.alumno("Hermano B", g, self.pagador)
        cuotas = [pricing.calcular_cuota_alumno(x)["cuota"] for x in (a, b)]
        self.assertAlmostEqual(sum(cuotas), 95.0, places=2)

    def test_hermanos_con_distintos_dias_precio_manual(self):
        a = self.alumno("Hermano A", self.grupo(1), self.pagador)
        self.alumno("Hermano B", self.grupo(2), self.pagador)
        r = pricing.calcular_cuota_alumno(a)
        self.assertEqual(r["tipo"], "sin_tabla")
        self.assertIsNone(r["cuota"])
        self.assertTrue(r["avisos"])

    def test_tres_hermanos_precio_manual(self):
        g = self.grupo(1)
        a = self.alumno("Hermano A", g, self.pagador)
        self.alumno("Hermano B", g, self.pagador)
        self.alumno("Hermano C", g, self.pagador)
        r = pricing.calcular_cuota_alumno(a)
        self.assertEqual(r["tipo"], "sin_tabla")
        self.assertIsNone(r["cuota"])

    def test_privadas_sin_calculo_automatico(self):
        a = self.alumno("Priv", None, codigo_clase="PRIVADA")
        r = pricing.calcular_cuota_alumno(a)
        self.assertEqual((r["tipo"], r["cuota"], r["tarifa_hora_referencia"]), ("privada_manual", None, 30))
        b = self.alumno("Prof", None, codigo_clase="PRIVADA_PROFESIONAL")
        r = pricing.calcular_cuota_alumno(b)
        self.assertEqual(r["tarifa_hora_referencia"], 35)

    def test_cuota_manual_tiene_prioridad(self):
        a = self.alumno("Manual", self.grupo(2), cuota_manual=80)
        r = pricing.calcular_cuota_alumno(a)
        self.assertEqual((r["tipo"], r["cuota"]), ("manual", 80.0))


class CalculadoraPagadorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="owner2@test.local", username="owner2", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def crear(self, nombre_pagador, perfiles):
        pagador = Pagador.objects.create(academia=self.user, nombre=nombre_pagador)
        for i, (dias, ini, fin) in enumerate(perfiles):
            g = Grupo.objects.create(
                academia=self.user, nombre=f"{nombre_pagador}-{i}",
                horarios=[{"dia": d, "ini": ini, "fin": fin} for d in range(dias)],
            )
            a = Alumno.objects.create(academia=self.user, nombre=f"{nombre_pagador} {i}", pagador=pagador)
            Inscripcion.objects.create(alumno=a, grupo=g)
        return pagador

    def fila(self, nombre):
        r = self.client.get("/api/v1/pagadores/calculadora/")
        self.assertEqual(r.status_code, 200)
        return next(x for x in r.json() if x["pagador_nombre"] == nombre)

    def test_bono_familia_tabla_fija(self):
        self.crear("Iguales", [(2, "17:00", "18:30"), (2, "17:00", "18:30")])
        f = self.fila("Iguales")
        self.assertEqual(f["cuota_mensual_estimada"], 260.0)
        self.assertEqual(f["items"][0]["tipo"], "bono_familia")

    def test_hermanos_distintos_sin_estimacion_automatica(self):
        self.crear("Distintos", [(1, "17:00", "18:00"), (3, "17:00", "18:00")])
        f = self.fila("Distintos")
        self.assertEqual(f["items"], [])
        self.assertEqual(f["cuota_mensual_estimada"], 0.0)
        self.assertTrue(f["avisos"])

    def test_alumno_solo_clase_grupo(self):
        self.crear("Solo", [(1, "17:00", "18:30")])
        f = self.fila("Solo")
        self.assertEqual(f["cuota_mensual_estimada"], 75.0)
