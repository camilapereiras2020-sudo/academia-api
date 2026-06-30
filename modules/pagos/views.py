from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.utils import timezone
from .models import Pago
from .serializers import PagoSerializer
from .constants import METODOS_FACTURA


def _send_payment_email(pago, num_doc, emisor_nombre="Cami&Co"):
    from django.conf import settings
    import resend

    email   = getattr(pago.pagador, "email", "") or ""
    api_key = getattr(settings, "RESEND_API_KEY", "") or ""
    if not email or not api_key or api_key == "re_placeholder":
        return

    resend.api_key     = api_key
    metodo_display     = (pago.metodo or "").capitalize()
    alumno_nombre      = pago.alumno.nombre
    pagador_nombre     = pago.pagador.nombre
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


def _resolve_emisor(user, emisor_id=None):
    """Return the Emisor for this pago. Defaults to camiandco if not specified."""
    from modules.documentos.models import Emisor
    if emisor_id:
        try:
            return Emisor.objects.get(id=emisor_id, academia=user)
        except Emisor.DoesNotExist:
            pass
    return Emisor.objects.filter(academia=user, slug="camiandco").first()


class PagoViewSet(ModelViewSet):
    serializer_class   = PagoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Pago.objects.filter(
            academia=self.request.user
        ).select_related("pagador", "alumno", "grupo", "emisor")
        estado  = self.request.query_params.get("estado")
        periodo = self.request.query_params.get("periodo")
        alumno  = self.request.query_params.get("alumno")
        pagador = self.request.query_params.get("pagador")
        if estado:  qs = qs.filter(estado=estado)
        if periodo: qs = qs.filter(periodo=periodo)
        if alumno:  qs = qs.filter(alumno_id=alumno)
        if pagador: qs = qs.filter(pagador_id=pagador)
        return qs

    def perform_create(self, serializer):
        emisor = _resolve_emisor(self.request.user, self.request.data.get("emisor"))
        pago   = serializer.save(academia=self.request.user, emisor=emisor)

        if not emisor:
            print(f"[invoice] no emisor found for pago {pago.id} — skipping PDF generation")
            return

        try:
            from modules.documentos.invoice_service import generate_invoice_for_pago
            from modules.documentos.models import Documento
            tipo = "factura" if pago.metodo.lower() in METODOS_FACTURA else "recibo"
            num_doc, drive_id = generate_invoice_for_pago(pago, tipo)
            Documento.objects.create(
                academia   = pago.academia,
                pago       = pago,
                tipo       = tipo,
                nombre     = f"{num_doc}.pdf",
                num_doc    = num_doc,
                s3_key     = drive_id,
                local_path = "",
                mime_type  = "application/pdf",
            )
            pago.num_doc = num_doc
            pago.save(update_fields=["num_doc"])
            try:
                _send_payment_email(pago, num_doc, emisor.nombre)
            except Exception as e:
                print(f"[email] notification failed for pago {pago.id}: {e}")
        except Exception as e:
            err = str(e)
            print(f"[invoice] auto-generate failed for pago {pago.id}: {err}")
            note = f"⚠ Factura no generada: {err}"
            pago.notas = ((pago.notas or "") + "\n" + note).strip()
            pago.save(update_fields=["notas"])

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
