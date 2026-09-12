import logging

from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.utils import timezone
from modules.authentication.rbac import ReadOnlyForReception, marca_scope_for
from .models import Pago
from .serializers import PagoSerializer, PagoReceptionSerializer

logger = logging.getLogger(__name__)


def _send_payment_email(pago, num_doc, emisor_nombre="Cami&Co"):
    from django.conf import settings
    import os
    import resend

    if os.environ.get("EMAIL_SENDING_ENABLED", "false").lower() != "true":
        logger.info("EMAIL_SENDING_ENABLED is off — skipping payment email for pago %s", pago.id)
        return

    # An adult alumno who pays for themself (Alumno.es_adulto) may have no
    # Pagador on file — same fallback as invoice_service._pagador_display_fields.
    if not pago.alumno or not (pago.pagador or getattr(pago.alumno, "es_adulto", False)):
        return  # incomplete pago — nothing to email yet

    pagador_obj = pago.pagador or pago.alumno
    email   = getattr(pagador_obj, "email", "") or ""
    api_key = getattr(settings, "RESEND_API_KEY", "") or ""
    if not email:
        logger.warning("Pago %s: pagador has no email on file — payment confirmation not sent", pago.id)
        return
    if not api_key or api_key == "re_placeholder":
        logger.error("RESEND_API_KEY is missing/placeholder — payment confirmation for pago %s not sent", pago.id)
        return

    resend.api_key     = api_key
    metodo_display     = (pago.metodo or "").capitalize()
    alumno_nombre      = pago.alumno.nombre
    pagador_nombre     = pagador_obj.nombre
    total_fmt          = "{:,.2f}".format(float(pago.total)).replace(",", "X").replace(".", ",").replace("X", ".")
    nombre_display     = emisor_nombre

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#2D2D2D;">
      <div style="border-bottom:3px solid #B08D57;padding-bottom:12px;margin-bottom:20px;">
        <h2 style="color:#B08D57;margin:0;">{nombre_display} — Confirmación de pago</h2>
      </div>
      <p>Estimado/a <strong>{pagador_nombre}</strong>,</p>
      <p>Hemos registrado correctamente tu pago. A continuación encontrarás el resumen:</p>
      <table style="width:100%;border-collapse:collapse;margin:20px 0;font-size:14px;">
        <tr style="background:#F7F5F2;">
          <td style="padding:10px 12px;border-bottom:1px solid #ddd;"><strong>Alumno/a</strong></td>
          <td style="padding:10px 12px;border-bottom:1px solid #ddd;">{alumno_nombre}</td>
        </tr>
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #ddd;"><strong>Importe</strong></td>
          <td style="padding:10px 12px;border-bottom:1px solid #ddd;">{total_fmt} €</td>
        </tr>
        <tr style="background:#F7F5F2;">
          <td style="padding:10px 12px;border-bottom:1px solid #ddd;"><strong>Método de pago</strong></td>
          <td style="padding:10px 12px;border-bottom:1px solid #ddd;">{metodo_display}</td>
        </tr>
        <tr>
          <td style="padding:10px 12px;"><strong>Nº de documento</strong></td>
          <td style="padding:10px 12px;">{num_doc}</td>
        </tr>
      </table>
      <p>
        Muchas gracias por confiar en {nombre_display}. Es un placer acompañar a
        <strong>{alumno_nombre}</strong> en su aprendizaje del inglés. 🎉
      </p>
      <p style="color:#6B6B6B;font-size:12px;">
        Si tienes cualquier duda, no dudes en ponerte en contacto con nosotros.
      </p>
      <p style="color:#B08D57;margin-top:24px;"><strong>{nombre_display} — Academia de inglés</strong></p>
    </div>
    """

    resend.Emails.send({
        "from": settings.DEFAULT_FROM_EMAIL,
        "to": [email],
        "subject": f"Confirmación de pago — {num_doc}",
        "html": html,
    })


MARCA_TO_EMISOR_SLUG = {
    "cami_and_co": "camiandco",
    "rangers_academy": "rangers",
}


def _resolve_emisor(user, emisor_id=None, marca=None):
    """Return the Emisor for this pago: un emisor_id explícito siempre gana;
    si no, se resuelve según la marca del pago (cada marca tiene su propia
    identidad fiscal — NIF, numeración, IBAN), y solo cae a camiandco si no
    hay marca reconocida."""
    from modules.documentos.models import Emisor
    if emisor_id:
        try:
            return Emisor.objects.get(id=emisor_id, academia=user)
        except Emisor.DoesNotExist:
            pass
    slug = MARCA_TO_EMISOR_SLUG.get(marca, "camiandco")
    return Emisor.objects.filter(academia=user, slug=slug).first()


class PagoViewSet(ModelViewSet):
    serializer_class   = PagoSerializer
    permission_classes = [permissions.IsAuthenticated, ReadOnlyForReception]

    def get_serializer_class(self):
        if self.request.user.role == "reception":
            return PagoReceptionSerializer
        return PagoSerializer

    def get_queryset(self):
        qs = Pago.objects.filter(
            academia=self.request.user.tenant
        ).select_related("pagador", "alumno", "grupo", "emisor")
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(marca=scope)
        estado  = self.request.query_params.get("estado")
        periodo = self.request.query_params.get("periodo")
        alumno  = self.request.query_params.get("alumno")
        pagador = self.request.query_params.get("pagador")
        marca   = self.request.query_params.get("marca")
        estado_carga = self.request.query_params.get("estado_carga")
        if estado:  qs = qs.filter(estado=estado)
        if periodo: qs = qs.filter(periodo=periodo)
        if alumno:  qs = qs.filter(alumno_id=alumno)
        if pagador: qs = qs.filter(pagador_id=pagador)
        if marca:   qs = qs.filter(marca=marca)
        if estado_carga: qs = qs.filter(estado_carga=estado_carga)
        return qs

    @action(detail=True, methods=["get"], url_path="preview-factura")
    def preview_factura(self, request, pk=None):
        """Unnumbered, watermarked look at what this pago's invoice/receipt
        would look like — for reviewing before "Confirmar factura" actually
        assigns a número. Pure rendering, no DB writes."""
        from django.http import HttpResponse
        from modules.documentos.invoice_service import generate_preview_pdf_bytes

        pago = self.get_object()
        try:
            pdf_bytes = generate_preview_pdf_bytes(pago)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="borrador-{pago.id}.pdf"'
        return response

    @action(detail=False, methods=["post"], url_path="generar-mes")
    def generar_mes(self, request):
        """Mid-month bulk draft generation: one un-invoiced Pago per actively
        enrolled alumno, priced off their (first, by name) assigned Grupo's
        tarifa — same "solo se exportó X, revisar el resto a mano" simplification
        already used by export_alumnos_to_sheet.py for a multi-grupo alumno.
        Nothing here ever gets a número/PDF/email — these are exactly the
        same kind of "completo pero sin facturar" pago a manually-created one
        is; staff reviews/adjusts (family discounts, extras, matrícula) and
        confirms each one same as always. Safe to re-run for the same
        periodo — an alumno who already has one is skipped, not duplicated.
        """
        periodo = (request.data.get("periodo") or "").strip() or timezone.now().strftime("%Y-%m")

        from modules.alumnos.models import Alumno

        alumnos_qs = Alumno.objects.filter(
            academia=request.user.tenant, activo=True, empresa__isnull=True,
        ).prefetch_related("inscripciones__grupo").select_related("pagador")
        scope = marca_scope_for(request.user)
        if scope:
            alumnos_qs = alumnos_qs.filter(marca=scope)

        ya_facturados = set(
            Pago.objects.filter(academia=request.user.tenant, periodo=periodo)
            .values_list("alumno_id", flat=True)
        )

        creados, omitidos = [], []
        for alumno in alumnos_qs:
            if alumno.id in ya_facturados:
                continue

            inscripciones = sorted(alumno.inscripciones.all(), key=lambda i: i.grupo.nombre)
            if not inscripciones:
                omitidos.append({"alumno": alumno.nombre, "motivo": "Sin grupo asignado."})
                continue
            grupo = inscripciones[0].grupo
            if len(inscripciones) > 1:
                omitidos_note = f"Matriculado en {len(inscripciones)} grupos, se usó '{grupo.nombre}' — revisar el resto a mano."
            else:
                omitidos_note = None

            if not alumno.pagador_id and not alumno.es_adulto:
                omitidos.append({"alumno": alumno.nombre, "motivo": "Sin pagador asignado."})
                continue

            emisor = _resolve_emisor(request.user.tenant, None, alumno.marca)
            if not emisor:
                omitidos.append({"alumno": alumno.nombre, "motivo": f"Sin emisor configurado para {alumno.marca}."})
                continue

            pago = Pago.objects.create(
                academia=request.user.tenant, marca=alumno.marca, emisor=emisor,
                alumno=alumno, pagador=alumno.pagador, grupo=grupo,
                periodo=periodo, mensualidad=grupo.tarifa, descuento=0, extras=[],
                total=grupo.tarifa, metodo=alumno.pagador.metodo if alumno.pagador else "",
                estado="pendiente", estado_carga="completo",
                notas=f"Generado automáticamente para {periodo}." + (f" {omitidos_note}" if omitidos_note else ""),
            )
            creados.append({"pago_id": pago.id, "alumno": alumno.nombre, "total": str(pago.total)})
            if omitidos_note:
                omitidos.append({"alumno": alumno.nombre, "motivo": omitidos_note, "aviso": True})

        return Response({"periodo": periodo, "creados": creados, "omitidos": omitidos})

    @action(detail=False, methods=["get"], url_path="sugerencias")
    def sugerencias(self, request):
        """For each pendiente_completar draft, suggest an alumno/pagador (and
        the matched alumno's grupo, if any) by fuzzy-matching concepto_original.
        Read-only — no writes, no invoice generation, no external calls.
        """
        from modules.alumnos.models import Alumno
        from modules.pagadores.models import Pagador
        from modules.grupos.models import Grupo
        from .models import ConceptoAlias
        from .matching import best_match

        scope = marca_scope_for(request.user)

        drafts = Pago.objects.filter(
            academia=request.user.tenant, estado_carga="pendiente_completar"
        ).select_related("emisor").order_by("numero_factura_reservado", "fecha")
        if scope:
            drafts = drafts.filter(marca=scope)

        alumnos_all_qs = Alumno.objects.filter(academia=request.user.tenant)
        if scope:
            alumnos_all_qs = alumnos_all_qs.filter(marca=scope)
        alumnos_qs = alumnos_all_qs.prefetch_related("grupos")
        alumno_candidates = [(a.id, a.nombre) for a in alumnos_qs]
        # A student can be in more than one class now — the suggestion only
        # needs *a* plausible grupo, so we just take the first membership.
        grupo_by_alumno = {a.id: a.grupos.all()[0].id for a in alumnos_qs if a.grupos.all()}
        pagadores_qs = Pagador.objects.filter(academia=request.user.tenant)
        if scope:
            pagadores_qs = pagadores_qs.filter(alumnos__marca=scope).distinct()
        pagador_candidates = list(pagadores_qs.values_list("id", "nombre"))
        grupo_nombres_qs = Grupo.objects.filter(academia=request.user.tenant)
        if scope:
            grupo_nombres_qs = grupo_nombres_qs.filter(marca=scope)
        grupo_nombres = dict(grupo_nombres_qs.values_list("id", "nombre"))

        alias_qs = ConceptoAlias.objects.filter(academia=request.user.tenant)
        aliases_alumno  = {a.alias_text: a.alumno_id  for a in alias_qs if a.alumno_id}
        aliases_pagador = {a.alias_text: a.pagador_id for a in alias_qs if a.pagador_id}

        rows = []
        for pago in drafts:
            sug_alumno  = best_match(pago.concepto_original, alumno_candidates, aliases=aliases_alumno)
            sug_pagador = best_match(pago.concepto_original, pagador_candidates, aliases=aliases_pagador)
            sug_grupo   = None
            if sug_alumno:
                gid = grupo_by_alumno.get(sug_alumno["id"])
                if gid:
                    sug_grupo = {"id": gid, "nombre": grupo_nombres.get(gid, "")}
            rows.append({
                "pago": PagoSerializer(pago).data,
                "sugerencia_alumno": sug_alumno,
                "sugerencia_pagador": sug_pagador,
                "sugerencia_grupo": sug_grupo,
            })
        return Response(rows)

    def perform_create(self, serializer):
        scope = marca_scope_for(self.request.user)
        if scope and serializer.validated_data.get("marca") != scope:
            raise PermissionDenied(f"Solo podés crear pagos de la marca {scope}.")
        emisor = _resolve_emisor(self.request.user.tenant, self.request.data.get("emisor"), serializer.validated_data.get("marca"))
        pago   = serializer.save(academia=self.request.user.tenant, emisor=emisor)

        if self.request.data.get("guardar_como_borrador"):
            # Manual "save as draft" — estado_carga is read-only on the
            # serializer (so a client can't set it directly), so this is a
            # deliberate request-level signal instead. Same fate as a
            # bulk-imported draft: no number, no invoice, until completed.
            pago.estado_carga = "pendiente_completar"
            pago.save(update_fields=["estado_carga"])
            return

        # Invoicing is never automatic (2026-09 redesign): a pago is created
        # "completo" but un-invoiced — no num_doc, no PDF, no email — until
        # staff explicitly confirms it (DocumentoViewSet.generar/generar_combinado).
        # While the platform's still being tested, an auto-assigned number on
        # a pago that turns out to have a mistake would need a formal anulación
        # to correct; a draft that was never confirmed just gets fixed and
        # confirmed once it's right.

    def perform_update(self, serializer):
        scope = marca_scope_for(self.request.user)
        if scope:
            new_marca = serializer.validated_data.get("marca", serializer.instance.marca)
            if new_marca != scope:
                raise PermissionDenied(f"Solo podés editar pagos de la marca {scope}.")
        was_pending = serializer.instance.estado_carga == "pendiente_completar"
        pago = serializer.save()

        # An adult alumno who pays for themself (Alumno.es_adulto) may have no
        # Pagador on file — generate_invoice_for_pago falls back to the
        # alumno's own contact data in that case, so don't gate completion on
        # pagador_id alone.
        if was_pending and pago.alumno_id and (
            pago.pagador_id or getattr(pago.alumno, "es_adulto", False)
        ):
            if not pago.emisor_id:
                pago.emisor = _resolve_emisor(self.request.user.tenant, self.request.data.get("emisor"), pago.marca)
            pago.estado_carga = "completo"
            pago.save(update_fields=["estado_carga", "emisor"])
            # Completing a draft no longer auto-invoices either — see
            # perform_create's comment. Staff confirms explicitly once it's
            # been reviewed, same as any other completo, un-invoiced pago.

    def destroy(self, request, *args, **kwargs):
        pago = self.get_object()
        if any(doc.is_issued for doc in pago.documentos.all()):
            return Response(
                {"error": "Este pago tiene documentos emitidos: anúlalos en vez de eliminar el pago."},
                status=status.HTTP_409_CONFLICT,
            )
        # Unlike the primary side (Documento.pago, on_delete=PROTECT), a
        # ManyToManyField gives no DB-level protection for the "additional"
        # side — deleting a Pago that's only bundled into someone else's
        # combined invoice would silently detach it from that invoice with
        # no error. Same guard as above, just covering the other side.
        if any(doc.is_issued for doc in pago.documentos_combinados.all()):
            return Response(
                {"error": "Este pago forma parte de una factura combinada emitida: anúlala en vez de eliminar el pago."},
                status=status.HTTP_409_CONFLICT,
            )
        # Documento.pago is on_delete=PROTECT now (an issued Documento must
        # never cascade-delete) — but a lingering borrador Documento (never
        # actually issued, no Drive/local file) is meant to be freely
        # discardable along with its draft Pago, so it's cleaned up
        # explicitly here rather than relying on cascade.
        pago.documentos.filter(estado="borrador").delete()
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="anular")
    def anular(self, request, pk=None):
        from modules.documentos.invoice_service import regenerate_anulada_pdf
        from modules.documentos.sheets_log import log_anulacion

        pago = self.get_object()
        motivo = (request.data.get("motivo_anulacion") or "").strip()
        if not motivo:
            return Response({"error": "motivo_anulacion es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        docs = [d for d in pago.documentos.all() if d.is_issued and d.estado != "anulada"]
        if not docs:
            return Response({"error": "No hay documentos emitidos para anular."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        for doc in docs:
            try:
                doc.s3_key = regenerate_anulada_pdf(doc)
            except Exception as e:
                return Response(
                    {"error": f"Error regenerando PDF anulado ({doc.num_doc}): {e}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            doc.estado, doc.anulada_at, doc.motivo_anulacion = "anulada", now, motivo
            doc.save(update_fields=["estado", "anulada_at", "motivo_anulacion", "s3_key"])
            try:
                log_anulacion(doc)
            except Exception as e:
                print(f"[anular] sheet log failed (non-critical): {e}")

        return Response(PagoSerializer(pago).data)

    @action(detail=True, methods=["post"], url_path="marcar-pagado")
    def marcar_pagado(self, request, pk=None):
        pago = self.get_object()
        pago.estado = "pagado"
        pago.fecha  = timezone.now().date()
        pago.save(update_fields=["estado", "fecha"])
        return Response(PagoSerializer(pago).data)

    @action(detail=True, methods=["post"], url_path="stripe-intent")
    def stripe_intent(self, request, pk=None):
        import stripe
        from django.conf import settings
        stripe.api_key = settings.STRIPE_SECRET_KEY
        pago   = self.get_object()
        intent = stripe.PaymentIntent.create(
            amount   = int(float(pago.total) * 100),
            currency = "eur",
            metadata = {"pago_id": pago.id},
        )
        pago.stripe_payment_intent = intent.id
        pago.save(update_fields=["stripe_payment_intent"])
        return Response({"client_secret": intent.client_secret})
