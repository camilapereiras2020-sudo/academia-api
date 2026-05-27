from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.utils import timezone
from .models import Pago
from .serializers import PagoSerializer


def generate_num_doc(user, serie_id="CC"):
    """Generate next sequential invoice number like CC-2026-001"""
    year = timezone.now().year
    last = (
        Pago.objects.filter(academia=user, serie_id=serie_id, num_doc__startswith=f"{serie_id}-{year}-")
        .order_by("-num_doc")
        .first()
    )
    if last and last.num_doc:
        try:
            seq = int(last.num_doc.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{serie_id}-{year}-{seq:03d}", serie_id


class PagoViewSet(ModelViewSet):
    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Pago.objects.filter(academia=self.request.user).select_related("pagador", "alumno", "grupo")
        estado = self.request.query_params.get("estado")
        periodo = self.request.query_params.get("periodo")
        alumno = self.request.query_params.get("alumno")
        pagador = self.request.query_params.get("pagador")
        if estado: qs = qs.filter(estado=estado)
        if periodo: qs = qs.filter(periodo=periodo)
        if alumno: qs = qs.filter(alumno_id=alumno)
        if pagador: qs = qs.filter(pagador_id=pagador)
        return qs

    def perform_create(self, serializer):
        num_doc, serie_id = generate_num_doc(self.request.user)
        serializer.save(academia=self.request.user, num_doc=num_doc, serie_id=serie_id)

    @action(detail=True, methods=["post"], url_path="marcar-pagado")
    def marcar_pagado(self, request, pk=None):
        pago = self.get_object()
        pago.estado = "pagado"
        pago.fecha = timezone.now().date()
        pago.save(update_fields=["estado", "fecha"])
        return Response(PagoSerializer(pago).data)

    @action(detail=True, methods=["post"], url_path="stripe-intent")
    def stripe_intent(self, request, pk=None):
        import stripe
        from django.conf import settings
        stripe.api_key = settings.STRIPE_SECRET_KEY
        pago = self.get_object()
        intent = stripe.PaymentIntent.create(
            amount=int(float(pago.total) * 100),
            currency="eur",
            metadata={"pago_id": pago.id}
        )
        pago.stripe_payment_intent = intent.id
        pago.save(update_fields=["stripe_payment_intent"])
        return Response({"client_secret": intent.client_secret})
