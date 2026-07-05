"""Tests for the bulk-import draft-completion workflow.

matching.py tests are pure functions — no DB access. The API/view tests use
Django's TestCase (isolated per-test database, created and destroyed
automatically — never touches dev or production data) and mock every
external call (Drive upload, email) so running these can never trigger a
real invoice generation or send a real email.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from modules.alumnos.models import Alumno
from modules.pagadores.models import Pagador
from modules.grupos.models import Grupo
from modules.documentos.models import Emisor
from modules.pagos.models import Pago
from modules.pagos.matching import best_match, _tokenize

User = get_user_model()

# Real concepto_original strings from t2_pagos_import.csv, used here only as
# literal test fixtures — this test never touches the actual CSV, the
# database it was imported into, or production.
REAL_CONCEPTOS = [
    "Ingreso Bizum - Abril",
    "Ingreso Bizum - Clases Febrero Camila Juan",
    "Ramirez Gonzalez Arturo",
    "Ingreso Bizum - English Classes Tete",
    "Ingreso Bizum - Juan B",
    "Ingreso Bizum - Lucas Valenzuela Abril Medio Mes",
    "Ingreso Bizum - (sin nombre)",
    "Ingreso Bizum - Alma V Abril Y Mayo Ingles",
    "Ingreso Bizum - Junio 26 Alma Said Valcarce",
]

CANDIDATE_ALUMNOS = [
    (1, "Alma Rial"),
    (2, "Juan López"),
    (3, "Lucas Valenzuela"),
    (4, "Alba Ramírez Martín"),
    (5, "Manuel Araujo"),
]


class MatchingTests(TestCase):
    def test_exact_full_name_match_scores_high(self):
        result = best_match("Ingreso Bizum - Lucas Valenzuela Abril Medio Mes", CANDIDATE_ALUMNOS)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 3)
        self.assertGreaterEqual(result["score"], 0.9)

    def test_name_embedded_in_longer_concepto(self):
        result = best_match("Ingreso Bizum - Clases Febrero Camila Juan Lopez", CANDIDATE_ALUMNOS)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 2)

    def test_no_name_present_returns_none(self):
        result = best_match("Ingreso Bizum - (sin nombre)", CANDIDATE_ALUMNOS)
        self.assertIsNone(result)

    def test_unrelated_surname_overlap_does_not_false_positive(self):
        # "Ramirez Gonzalez Arturo" shares only "Ramirez" with "Alba Ramírez
        # Martín" — a different person. Must not match on a single shared
        # surname token alone.
        result = best_match("Ramirez Gonzalez Arturo", CANDIDATE_ALUMNOS)
        self.assertIsNone(result)

    def test_partial_first_name_medium_confidence(self):
        result = best_match("Ingreso Bizum - Alma V Abril Y Mayo Ingles", CANDIDATE_ALUMNOS)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 1)
        self.assertLess(result["score"], 0.9)  # partial, not exact

    def test_empty_concepto_returns_none(self):
        self.assertIsNone(best_match("", CANDIDATE_ALUMNOS))
        self.assertIsNone(best_match(None, CANDIDATE_ALUMNOS))

    def test_no_candidates_returns_none(self):
        self.assertIsNone(best_match("Juan Lopez", []))

    def test_month_names_and_numbers_are_stripped_as_noise(self):
        tokens = _tokenize("Ingreso Bizum - Junio 26 Alma Said Valcarce")
        self.assertNotIn("junio", tokens)
        self.assertNotIn("26", tokens)
        self.assertIn("alma", tokens)

    def test_all_real_csv_conceptos_do_not_crash(self):
        for concepto in REAL_CONCEPTOS:
            best_match(concepto, CANDIDATE_ALUMNOS)  # just must not raise


class DraftCompletionFlowTests(TestCase):
    """Verifies the suggestions endpoint and the existing PATCH-completes-draft
    flow, with every external side effect (Drive, email) mocked out.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.emisor = Emisor.objects.create(
            academia=self.user, slug="camiandco", nombre="Cami&Co",
            autonoma="Test", nif="X", direccion="X", ciudad="X",
            factura_prefix="CC", recibo_prefix="RE",
        )
        self.grupo = Grupo.objects.create(academia=self.user, nombre="Grupo A", nivel="B1", tarifa=50)
        self.alumno = Alumno.objects.create(academia=self.user, nombre="Juan Lopez", grupo=self.grupo)
        self.pagador = Pagador.objects.create(academia=self.user, nombre="Juan Lopez")

        self.draft = Pago.objects.create(
            academia=self.user, emisor=self.emisor, marca="cami_and_co",
            alumno=None, pagador=None, grupo=None,
            periodo="2026-04", fecha="2026-04-05",
            mensualidad=0, descuento=0, extras=[], total=65,
            metodo="transferencia", estado="pagado",
            concepto_original="Ingreso Bizum - Clases Febrero Camila Juan Lopez",
            numero_factura_reservado="CC252-26",
            estado_carga="pendiente_completar",
        )

    def test_suggestions_endpoint_matches_juan_lopez(self):
        resp = self.client.get("/api/v1/pagos/sugerencias/")
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["pago"]["id"], self.draft.id)
        self.assertIsNotNone(row["sugerencia_alumno"])
        self.assertEqual(row["sugerencia_alumno"]["id"], self.alumno.id)
        self.assertIsNotNone(row["sugerencia_pagador"])
        self.assertEqual(row["sugerencia_pagador"]["id"], self.pagador.id)
        # alumno has a grupo -> should be suggested too
        self.assertEqual(row["sugerencia_grupo"]["id"], self.grupo.id)

    @patch("modules.pagos.views._send_payment_email")
    @patch("modules.documentos.invoice_service.generate_invoice_for_pago")
    def test_patch_completes_draft_and_calls_generation_exactly_once(self, mock_generate, mock_email):
        mock_generate.return_value = ("CC252-26", "fake-drive-id")

        resp = self.client.patch(
            f"/api/v1/pagos/{self.draft.id}/",
            {"alumno": self.alumno.id, "pagador": self.pagador.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)

        self.draft.refresh_from_db()
        self.assertEqual(self.draft.estado_carga, "completo")
        self.assertEqual(self.draft.alumno_id, self.alumno.id)
        self.assertEqual(self.draft.pagador_id, self.pagador.id)
        mock_generate.assert_called_once()
        # confirms the reserved number path, not a freshly allocated one
        self.assertEqual(self.draft.num_doc, "CC252-26")

    def test_patch_without_alumno_pagador_stays_pending(self):
        resp = self.client.patch(
            f"/api/v1/pagos/{self.draft.id}/",
            {"notas": "still reviewing"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.estado_carga, "pendiente_completar")
        self.assertEqual(self.draft.num_doc, "")

    def test_cannot_null_alumno_on_already_issued_pago(self):
        from modules.documentos.models import Documento
        self.draft.alumno = self.alumno
        self.draft.pagador = self.pagador
        self.draft.estado_carga = "completo"
        self.draft.save()
        Documento.objects.create(
            academia=self.user, pago=self.draft, tipo="factura",
            nombre="x.pdf", num_doc="CC252-26", estado="emitida",
        )
        resp = self.client.patch(f"/api/v1/pagos/{self.draft.id}/", {"alumno": None}, format="json")
        self.assertEqual(resp.status_code, 400)
