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
        self.alumno = Alumno.objects.create(academia=self.user, nombre="Juan Lopez")
        self.alumno.grupos.add(self.grupo)
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

    def test_patch_completes_draft_without_auto_invoicing(self):
        """Completing a draft's missing alumno/pagador makes it "completo",
        but invoicing is never automatic (2026-09 redesign) — even a
        pre-reserved número (from a bulk import) stays reserved-but-unissued
        until staff explicitly confirms via documentos/generar."""
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
        self.assertEqual(self.draft.num_doc, "")
        self.assertFalse(self.draft.documentos.exists())

    @patch("modules.documentos.sheets_log.log_emision")
    @patch("modules.pagos.views._send_payment_email")
    @patch("modules.documentos.invoice_service.upload_to_drive")
    def test_create_pago_for_adult_alumno_without_pagador_succeeds(self, mock_upload, mock_email, mock_log_emision):
        mock_upload.return_value = "FAKE_DRIVE_ID"
        adulto = Alumno.objects.create(academia=self.user, nombre="Adulto Autopagador", es_adulto=True)

        resp = self.client.post(
            "/api/v1/pagos/",
            {
                "alumno": adulto.id, "pagador": None,
                "periodo": "2026-08", "total": 50, "mensualidad": 50, "descuento": 0,
                "metodo": "transferencia", "marca": "cami_and_co", "estado": "pagado",
                "fecha": "2026-08-16",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        pago = Pago.objects.get(id=resp.json()["id"])
        self.assertIsNone(pago.pagador_id)
        self.assertNotEqual(pago.num_doc, "")
        self.assertNotIn("Factura no generada", pago.notas or "")
        self.assertTrue(pago.documentos.filter(estado="emitida").exists())

    def test_create_pago_for_non_adult_alumno_without_pagador_creates_pago_but_skips_invoice(self):
        # Contrast case: a minor with no pagador still gets the Pago row (so the
        # data isn't lost), but invoice generation can't proceed without someone
        # to bill — that's the boundary the adult/es_adulto exception carves out.
        menor = Alumno.objects.create(academia=self.user, nombre="Menor Sin Pagador", es_adulto=False)

        resp = self.client.post(
            "/api/v1/pagos/",
            {
                "alumno": menor.id, "pagador": None,
                "periodo": "2026-08", "total": 50, "mensualidad": 50, "descuento": 0,
                "metodo": "transferencia", "marca": "cami_and_co", "estado": "pagado",
                "fecha": "2026-08-16",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        pago = Pago.objects.get(id=resp.json()["id"])
        self.assertIsNone(pago.pagador_id)
        self.assertIn("Factura no generada", pago.notas or "")
        self.assertFalse(pago.documentos.filter(estado="emitida").exists())

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

    def test_create_with_guardar_como_borrador_stays_pending(self):
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

    def test_create_without_guardar_como_borrador_never_auto_invoices(self):
        """2026-09 redesign: no pago ever gets a número/PDF/email just from
        being created — staff always confirms explicitly (documentos/generar
        or generar-combinado), so a mistake caught before confirming needs
        no formal anulación, just a fix."""
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
        self.assertEqual(pago.num_doc, "")
        self.assertFalse(pago.documentos.exists())

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
        the review screen's Save button issues -> stays un-invoiced (2026-09
        redesign: nothing is ever automatic) -> staff explicitly confirms
        (documentos/generar: real number allocation, real PDF generation) ->
        staff explicitly sends (documentos/enviar: real email-content
        building) -- only the three actual network calls (Drive upload,
        Resend send, Sheets log) are intercepted. EMAIL_SENDING_ENABLED is
        force-enabled for this test only, since it's specifically verifying
        the resend call gets made; the kill switch defaults to off everywhere
        else, and even then nothing sends without the explicit enviar call.
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
                "periodo": "2026-07", "fecha": "2026-07-15", "total": 123.45, "metodo": "transferencia",
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
        # Still no número, no PDF, no email -- completing a draft's data is
        # not the same thing as confirming its invoice.
        self.assertEqual(draft.num_doc, "")
        mock_upload.assert_not_called()
        mock_resend_send.assert_not_called()

        # 4) staff explicitly confirms -- this is the only thing that ever
        # assigns a número and renders/stores the real PDF
        generar_resp = self.client.post("/api/v1/documentos/generar/", {"pago_id": draft.id}, format="json")
        self.assertEqual(generar_resp.status_code, 201, generar_resp.content)
        documento_id = generar_resp.json()["id"]

        draft.refresh_from_db()
        self.assertTrue(draft.num_doc.startswith("CC"))
        self.assertNotEqual(draft.num_doc, "")

        # 5) inspect exactly what would have gone to Drive -- confirming does
        # upload, it just never emails on its own
        mock_upload.assert_called_once()
        pdf_bytes, filename, year, month, folder_id = mock_upload.call_args[0][:5]
        self.assertTrue(pdf_bytes[:4] == b"%PDF")   # a real PDF was actually built
        self.assertGreater(len(pdf_bytes), 1000)
        self.assertEqual(filename, f"{draft.num_doc}.pdf")
        self.assertEqual(year, 2026)
        self.assertEqual(month, 7)
        self.assertEqual(folder_id, "FAKE_FOLDER_ID_FOR_TEST")
        mock_resend_send.assert_not_called()

        # 6) staff explicitly sends -- only now does the email actually go out
        enviar_resp = self.client.post(f"/api/v1/documentos/{documento_id}/enviar/")
        self.assertEqual(enviar_resp.status_code, 200, enviar_resp.content)

        mock_resend_send.assert_called_once()
        email_payload = mock_resend_send.call_args[0][0]
        self.assertEqual(email_payload["to"], ["synthetic-e2e@example.test"])
        self.assertIn(draft.num_doc, email_payload["subject"])
        self.assertIn("Synthetic Alumno E2E", email_payload["html"])
        self.assertIn("Synthetic Pagador E2E", email_payload["html"])
        self.assertIn("123,45", email_payload["html"])  # eur-formatted total

        print("\n" + "=" * 70)
        print("DRIVE UPLOAD CALL (mocked -- nothing actually sent):")
        print(f"  filename={filename!r} year={year} month={month} folder_id={folder_id!r}")
        print(f"  pdf_bytes: {len(pdf_bytes)} bytes, starts with {pdf_bytes[:8]!r}")
        print("\nEMAIL SEND CALL (mocked -- nothing actually sent):")
        print(f"  to={email_payload['to']!r}")
        print(f"  subject={email_payload['subject']!r}")
        print(f"  from={email_payload['from']!r}")
        print(f"  full html length: {len(email_payload['html'])} chars")
        print("=" * 70)


class PreviewFacturaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="preview_user", email="preview@example.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.emisor = Emisor.objects.create(
            academia=self.user, slug="camiandco", nombre="Cami&Co", autonoma="Test",
            nif="X", direccion="X", ciudad="X", factura_prefix="CC", recibo_prefix="RE",
        )
        self.pagador = Pagador.objects.create(academia=self.user, nombre="Preview Pagador")
        self.alumno = Alumno.objects.create(academia=self.user, nombre="Preview Alumno", pagador=self.pagador)
        self.pago = Pago.objects.create(
            academia=self.user, emisor=self.emisor, marca="cami_and_co",
            alumno=self.alumno, pagador=self.pagador,
            periodo="2026-09", fecha="2026-09-01",
            mensualidad=80, descuento=0, extras=[], total=80,
            metodo="transferencia", estado="pendiente", estado_carga="completo",
        )

    def test_preview_returns_pdf_without_reserving_a_number(self):
        resp = self.client.get(f"/api/v1/pagos/{self.pago.id}/preview-factura/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content[:4] == b"%PDF")
        self.pago.refresh_from_db()
        self.assertEqual(self.pago.numero_factura_reservado, "")
        self.assertEqual(self.pago.num_doc, "")
        self.assertFalse(self.pago.documentos.exists())

    def test_preview_incomplete_pago_returns_400(self):
        incompleto = Pago.objects.create(
            academia=self.user, emisor=self.emisor, marca="cami_and_co",
            periodo="2026-09", fecha="2026-09-01",
            mensualidad=0, descuento=0, extras=[], total=0,
            metodo="", estado="pendiente", estado_carga="pendiente_completar",
        )
        resp = self.client.get(f"/api/v1/pagos/{incompleto.id}/preview-factura/")
        self.assertEqual(resp.status_code, 400)


class EnviarDocumentoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="enviar_user", email="enviar@example.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.emisor = Emisor.objects.create(
            academia=self.user, slug="camiandco", nombre="Cami&Co", autonoma="Test",
            nif="X", direccion="X", ciudad="X", factura_prefix="CC", recibo_prefix="RE",
        )
        self.pagador = Pagador.objects.create(academia=self.user, nombre="Enviar Pagador", email="enviar-pagador@example.test")
        self.alumno = Alumno.objects.create(academia=self.user, nombre="Enviar Alumno", pagador=self.pagador)
        self.pago = Pago.objects.create(
            academia=self.user, emisor=self.emisor, marca="cami_and_co",
            alumno=self.alumno, pagador=self.pagador,
            periodo="2026-09", fecha="2026-09-01",
            mensualidad=80, descuento=0, extras=[], total=80,
            metodo="transferencia", estado="pendiente", estado_carga="completo",
        )

    def test_enviar_rejects_unconfirmed_documento(self):
        from modules.documentos.models import Documento
        borrador = Documento.objects.create(
            academia=self.user, pago=self.pago, tipo="factura",
            nombre="x.pdf", num_doc="", estado="borrador",
        )
        resp = self.client.post(f"/api/v1/documentos/{borrador.id}/enviar/")
        self.assertEqual(resp.status_code, 400)

    @patch.dict(os.environ, {"EMAIL_SENDING_ENABLED": "false"})
    def test_enviar_off_when_email_sending_disabled(self):
        from modules.documentos.models import Documento
        doc = Documento.objects.create(
            academia=self.user, pago=self.pago, tipo="factura",
            nombre="CC1-26.pdf", num_doc="CC1-26", estado="emitida",
            pdf_data=b"%PDF-fake",
        )
        resp = self.client.post(f"/api/v1/documentos/{doc.id}/enviar/")
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("desactivado", resp.json()["error"])


class GenerarMesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mes_user", email="mes@example.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        Emisor.objects.create(
            academia=self.user, slug="camiandco", nombre="Cami&Co", autonoma="Test",
            nif="X", direccion="X", ciudad="X", factura_prefix="CC", recibo_prefix="RE",
        )
        Emisor.objects.create(
            academia=self.user, slug="rangers", nombre="Rangers Academy", autonoma="Test",
            nif="X2", direccion="X", ciudad="X", factura_prefix="RA", recibo_prefix="RR",
        )
        self.pagador = Pagador.objects.create(academia=self.user, nombre="Mes Pagador")
        self.grupo = Grupo.objects.create(academia=self.user, marca="cami_and_co", nombre="Mes Grupo", nivel="A1", tarifa=75)
        self.alumno = Alumno.objects.create(academia=self.user, nombre="Mes Alumno", marca="cami_and_co", pagador=self.pagador)
        self.alumno.grupos.add(self.grupo)

    def test_generar_mes_creates_one_undated_pago_per_alumno(self):
        resp = self.client.post("/api/v1/pagos/generar-mes/", {"periodo": "2026-09"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(len(data["creados"]), 1)
        self.assertEqual(data["creados"][0]["alumno"], "Mes Alumno")

        pago = Pago.objects.get(alumno=self.alumno, periodo="2026-09")
        self.assertEqual(pago.estado_carga, "completo")
        self.assertEqual(pago.num_doc, "")
        self.assertEqual(float(pago.total), 75.0)
        self.assertEqual(pago.pagador_id, self.pagador.id)

    def test_generar_mes_is_idempotent(self):
        self.client.post("/api/v1/pagos/generar-mes/", {"periodo": "2026-09"}, format="json")
        resp2 = self.client.post("/api/v1/pagos/generar-mes/", {"periodo": "2026-09"}, format="json")
        self.assertEqual(resp2.status_code, 200, resp2.content)
        self.assertEqual(len(resp2.json()["creados"]), 0)
        self.assertEqual(Pago.objects.filter(alumno=self.alumno, periodo="2026-09").count(), 1)

    def test_generar_mes_skips_alumno_without_grupo(self):
        Alumno.objects.create(academia=self.user, nombre="Sin Grupo", marca="cami_and_co", pagador=self.pagador)
        resp = self.client.post("/api/v1/pagos/generar-mes/", {"periodo": "2026-09"}, format="json")
        omitidos_nombres = [o["alumno"] for o in resp.json()["omitidos"]]
        self.assertIn("Sin Grupo", omitidos_nombres)

    def test_generar_mes_skips_alumno_without_pagador(self):
        Alumno.objects.create(academia=self.user, nombre="Sin Pagador", marca="cami_and_co").grupos.add(self.grupo)
        resp = self.client.post("/api/v1/pagos/generar-mes/", {"periodo": "2026-09"}, format="json")
        omitidos_nombres = [o["alumno"] for o in resp.json()["omitidos"]]
        self.assertIn("Sin Pagador", omitidos_nombres)

    def test_generar_mes_reception_forbidden(self):
        reception = User.objects.create_user(
            username="mes_reception", email="mesr@example.com", password="x",
            role="reception", academia_owner=self.user,
        )
        self.client.force_authenticate(reception)
        resp = self.client.post("/api/v1/pagos/generar-mes/", {"periodo": "2026-09"}, format="json")
        self.assertEqual(resp.status_code, 403)
