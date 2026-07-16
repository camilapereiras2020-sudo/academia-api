"""Tests for the bulk-import draft-completion workflow.

matching.py tests are pure functions — no DB access. The API/view tests use
Django's TestCase (isolated per-test database, created and destroyed
automatically — never touches dev or production data) and mock every
external call (Drive upload, email, Sheets logging) so running these can
never trigger a real invoice generation, send a real email, or write to the
real production Google Sheet. sheets_log.log_emision/log_anulacion also have
a hard runtime guard (config.settings.TESTING) that raises if a future test
ever reaches them unmocked, instead of silently hitting production.
"""
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
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

    def test_shared_surname_among_relatives_never_matches_without_given_name(self):
        # Real production scenario: four people share "Troncoso Gonzalo"
        # (two siblings, their aunt, their father). Concepto text with only
        # the surname must not pick any of them.
        relatives = [
            (1, "Álvaro Troncoso Gonzalo"),
            (2, "Victoria Troncoso Gonzalo"),
            (3, "Susana Troncoso Gonzalo"),
            (4, "Carlos Troncoso Gonzalo"),
        ]
        self.assertIsNone(best_match("Pago de Troncoso Gonzalo", relatives))

    def test_tie_between_equally_scored_candidates_returns_none(self):
        # Two different people both named "Juan", concepto only says "Juan"
        # — equally strong (or weak) evidence for both, must not guess.
        candidates = [(1, "Juan Perez"), (2, "Juan Garcia")]
        self.assertIsNone(best_match("Juan", candidates))

    def test_given_name_present_still_disambiguates_by_overlap_ratio(self):
        # Not a tie: "Juan Lopez" (2 tokens) scores higher than "Juan
        # Blazquez Sobral" (3 tokens) for the same single-token overlap.
        candidates = [(1, "Juan Lopez"), (2, "Juan Blazquez Sobral")]
        result = best_match("Juan", candidates)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 1)

    def test_alias_matches_before_token_logic(self):
        candidates = [(1, "Alba Ramírez Martín")]  # no given-name evidence for "Arturo" at all
        result = best_match("Ramirez Gonzalez Arturo", candidates, aliases={"Arturo": 1})
        self.assertEqual(result, {"id": 1, "nombre": "Alba Ramírez Martín", "score": 1.0})

    def test_alias_ignored_if_target_id_not_in_candidates(self):
        candidates = [(1, "Alba Ramírez Martín")]
        result = best_match("Ramirez Gonzalez Arturo", candidates, aliases={"Arturo": 999})
        self.assertIsNone(result)

    def test_nickname_alias_resolves_where_token_matching_would_not(self):
        candidates = [(25, "Tere")]
        result = best_match("Ingreso Bizum - English Classes Tete", candidates, aliases={"Tete": 25})
        self.assertEqual(result["id"], 25)
        self.assertEqual(result["score"], 1.0)

    def test_ma_prefix_does_not_become_a_spurious_given_name_token(self):
        # "Mª" (feminine ordinal indicator, not a precomposed accented
        # letter) doesn't survive NFD accent-stripping and gets replaced by
        # the tokenizer's punctuation regex, leaving a bare length-1 "m"
        # that the >=2-char filter drops -- so the given name correctly
        # ends up being "teresa", not "m". Neither "Tete" nor "Tere" share
        # any token with "teresa" though, so real-world resolution for
        # this pagador still needs the alias table (see
        # seed_concepto_alias.py), not token matching alone.
        self.assertEqual(_tokenize("Mª Teresa"), ["teresa"])
        self.assertIsNone(best_match("Ingreso Bizum - Clases Tere", [(19, "Mª Teresa")]))
        result = best_match(
            "Ingreso Bizum - Clases Tere", [(19, "Mª Teresa")], aliases={"Tere": 19},
        )
        self.assertEqual(result, {"id": 19, "nombre": "Mª Teresa", "score": 1.0})

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

    def test_suggestions_endpoint_uses_concepto_alias(self):
        from modules.pagos.models import ConceptoAlias

        tere = Alumno.objects.create(academia=self.user, nombre="Tere")
        nickname_draft = Pago.objects.create(
            academia=self.user, emisor=self.emisor, marca="cami_and_co",
            alumno=None, pagador=None, grupo=None,
            periodo="2026-04", fecha="2026-04-14",
            mensualidad=0, descuento=0, extras=[], total=25,
            metodo="transferencia", estado="pagado",
            concepto_original="Ingreso Bizum - English Classes Tete",
            numero_factura_reservado="CC257-26",
            estado_carga="pendiente_completar",
        )
        ConceptoAlias.objects.create(academia=self.user, alias_text="Tete", alumno=tere)

        resp = self.client.get("/api/v1/pagos/sugerencias/")
        self.assertEqual(resp.status_code, 200)
        row = next(r for r in resp.json() if r["pago"]["id"] == nickname_draft.id)
        self.assertEqual(row["sugerencia_alumno"]["id"], tere.id)
        self.assertEqual(row["sugerencia_alumno"]["score"], 1.0)

    @patch("modules.documentos.sheets_log.log_emision")
    @patch("modules.pagos.views._send_payment_email")
    @patch("modules.documentos.invoice_service.generate_invoice_for_pago")
    def test_patch_completes_draft_and_calls_generation_exactly_once(self, mock_generate, mock_email, mock_log_emision):
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

    @patch("modules.pagos.views._issue_invoice")
    def test_create_with_guardar_como_borrador_skips_invoice_and_stays_pending(self, mock_issue):
        resp = self.client.post(
            "/api/v1/pagos/",
            {
                "periodo": "2026-07", "total": 90, "metodo": "efectivo", "marca": "cami_and_co",
                "guardar_como_borrador": True,
                # alumno/pagador/grupo deliberately omitted, same as an import draft
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        pago = Pago.objects.get(id=resp.json()["id"])
        self.assertEqual(pago.estado_carga, "pendiente_completar")
        self.assertIsNone(pago.alumno_id)
        self.assertIsNone(pago.pagador_id)
        self.assertEqual(pago.num_doc, "")
        self.assertEqual(pago.numero_factura_reservado, "")
        mock_issue.assert_not_called()

    @patch("modules.pagos.views._issue_invoice")
    def test_create_without_guardar_como_borrador_issues_normally(self, mock_issue):
        resp = self.client.post(
            "/api/v1/pagos/",
            {
                "periodo": "2026-07", "total": 90, "metodo": "efectivo", "marca": "cami_and_co",
                "alumno": self.alumno.id, "pagador": self.pagador.id,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        pago = Pago.objects.get(id=resp.json()["id"])
        self.assertEqual(pago.estado_carga, "completo")
        mock_issue.assert_called_once()

    def test_create_without_marca_is_rejected(self):
        # marca has a model-level default ("rangers_academy") purely for
        # internal scripts (healthcheck.py) that don't care -- the real API
        # must never silently fall back to it. This is the actual bug
        # behind CC272/273/274-26 shipping tagged rangers_academy despite
        # being genuine Cami&Co invoices.
        resp = self.client.post(
            "/api/v1/pagos/",
            {"periodo": "2026-07", "total": 90, "metodo": "efectivo", "guardar_como_borrador": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("marca", resp.json())

    def test_manual_draft_appears_in_sugerencias_alongside_imported_ones(self):
        resp = self.client.post(
            "/api/v1/pagos/",
            {"periodo": "2026-07", "total": 40, "metodo": "efectivo", "marca": "cami_and_co", "guardar_como_borrador": True},
            format="json",
        )
        manual_draft_id = resp.json()["id"]

        rows = self.client.get("/api/v1/pagos/sugerencias/").json()
        ids = {r["pago"]["id"] for r in rows}
        self.assertIn(manual_draft_id, ids)   # the manually-created one
        self.assertIn(self.draft.id, ids)     # the pre-existing "imported" one from setUp
        manual_row = next(r for r in rows if r["pago"]["id"] == manual_draft_id)
        # no concepto_original -> nothing to fuzzy-match against -> no crash, no suggestion
        self.assertIsNone(manual_row["sugerencia_alumno"])
        self.assertIsNone(manual_row["sugerencia_pagador"])

    @override_settings(RESEND_API_KEY="test_key_for_pipeline_check")
    @patch.dict(os.environ, {"EMAIL_SENDING_ENABLED": "true"})
    @patch("modules.documentos.sheets_log.log_emision")
    @patch("resend.Emails.send")
    @patch("modules.documentos.invoice_service.upload_to_drive")
    def test_full_pipeline_end_to_end_with_mocked_external_calls(self, mock_upload, mock_resend_send, mock_log_emision):
        """Create -> appear in batch review -> complete via the exact same PATCH
        the review screen's Save button issues -> real number allocation, real
        PDF generation, real email-content building -- only the three actual
        network calls (Drive upload, Resend send, Sheets log) are intercepted.
        EMAIL_SENDING_ENABLED is force-enabled for this test only, since it's
        specifically verifying the resend call gets made; the kill switch
        defaults to off everywhere else.
        """
        mock_upload.return_value = "FAKE_DRIVE_FILE_ID_FOR_TEST"

        alumno = Alumno.objects.create(academia=self.user, nombre="Synthetic Alumno E2E")
        pagador = Pagador.objects.create(
            academia=self.user, nombre="Synthetic Pagador E2E", email="synthetic-e2e@example.test",
        )
        self.emisor.drive_folder_id = "FAKE_FOLDER_ID_FOR_TEST"
        self.emisor.save(update_fields=["drive_folder_id"])

        # 1) create a draft exactly as "Guardar como borrador" does
        create_resp = self.client.post(
            "/api/v1/pagos/",
            {
                "periodo": "2026-07", "total": 123.45, "metodo": "transferencia",
                "marca": "cami_and_co", "guardar_como_borrador": True,
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, 201, create_resp.content)
        draft_id = create_resp.json()["id"]
        mock_upload.assert_not_called()
        mock_resend_send.assert_not_called()

        # 2) confirm it's picked up by the same endpoint the batch-review screen reads
        sug_resp = self.client.get("/api/v1/pagos/sugerencias/")
        row = next(r for r in sug_resp.json() if r["pago"]["id"] == draft_id)
        self.assertEqual(row["pago"]["estado_carga"], "pendiente_completar")

        # 3) complete it -- exactly the PATCH the batch-review screen's per-row Save issues
        patch_resp = self.client.patch(
            f"/api/v1/pagos/{draft_id}/",
            {"alumno": alumno.id, "pagador": pagador.id},
            format="json",
        )
        self.assertEqual(patch_resp.status_code, 200, patch_resp.content)

        draft = Pago.objects.get(id=draft_id)
        self.assertEqual(draft.estado_carga, "completo")
        self.assertTrue(draft.num_doc.startswith("CC"))
        self.assertNotEqual(draft.num_doc, "")

        # 4) inspect exactly what would have gone to Drive
        mock_upload.assert_called_once()
        pdf_bytes, filename, year, month, folder_id = mock_upload.call_args[0][:5]
        self.assertTrue(pdf_bytes[:4] == b"%PDF")   # a real PDF was actually built
        self.assertGreater(len(pdf_bytes), 1000)
        self.assertEqual(filename, f"{draft.num_doc}.pdf")
        self.assertEqual(year, 2026)
        self.assertEqual(month, 7)
        self.assertEqual(folder_id, "FAKE_FOLDER_ID_FOR_TEST")

        # 5) inspect exactly what would have gone to the email API
        mock_resend_send.assert_called_once()
        email_payload = mock_resend_send.call_args[0][0]
        self.assertEqual(email_payload["to"], ["synthetic-e2e@example.test"])
        self.assertIn(draft.num_doc, email_payload["subject"])
        self.assertIn("Synthetic Alumno E2E", email_payload["html"])
        self.assertIn("Synthetic Pagador E2E", email_payload["html"])
        self.assertIn("123,45", email_payload["html"])  # eur-formatted total
        self.assertIn("Cami&Co", email_payload["html"])  # emisor name

        print("\n" + "=" * 70)
        print("DRIVE UPLOAD CALL (mocked -- nothing actually sent):")
        print(f"  filename={filename!r} year={year} month={month} folder_id={folder_id!r}")
        print(f"  pdf_bytes: {len(pdf_bytes)} bytes, starts with {pdf_bytes[:8]!r}")
        print("\nEMAIL SEND CALL (mocked -- nothing actually sent):")
        print(f"  to={email_payload['to']!r}")
        print(f"  subject={email_payload['subject']!r}")
        print(f"  from={email_payload['from']!r}")
        print(f"  html contains: num_doc={draft.num_doc in email_payload['html']}, "
              f"alumno={'Synthetic Alumno E2E' in email_payload['html']}, "
              f"pagador={'Synthetic Pagador E2E' in email_payload['html']}, "
              f"total='123,45' in html={'123,45' in email_payload['html']}, "
              f"emisor='Cami&Co' in html={'Cami&Co' in email_payload['html']}")
        print(f"  full html length: {len(email_payload['html'])} chars")
        print("=" * 70)
