from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.utils import timezone
from .models import Pago
from .serializers import PagoSerializer

class PagoViewSet(ModelViewSet):
    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Pago.objects.filter(academia=self.request.user).select_related("pagador", "alumno", "grupo")
        estado = self.request.query_params.get("estado")
        periodo = self.request.query_params.get("periodo")
        if estado: qs = qs.filter(estado=estado)
        if periodo: qs = qs.filter(periodo=periodo)
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user)

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
        intent = stripe.PaymentIntent.create(amount=int(float(pago.total) * 100), currency="eur", metadata={"pago_id": pago.id})
        pago.stripe_payment_intent = intent.id
        pago.save(update_fields=["stripe_payment_intent"])
        return Response({"client_secret": intent.client_secret})
