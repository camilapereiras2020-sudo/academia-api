from decimal import Decimal

from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import NotReception, marca_scope_for
from modules.core.mixins import ContactableViaPagadorMixin
from modules.pagos.models import Pago
from modules.tarifas.pricing import calcular_cuota_alumno
from .models import Pagador
from .serializers import PagadorSerializer


class PagadorViewSet(ContactableViaPagadorMixin, ModelViewSet):
    serializer_class = PagadorSerializer
    permission_classes = [permissions.IsAuthenticated, NotReception]

    def get_queryset(self):
        qs = Pagador.objects.filter(academia=self.request.user.tenant).prefetch_related("alumnos")
        scope = marca_scope_for(self.request.user)
        if scope:
            # A pagador with at least one child in the co_manager's marca is
            # visible in full (PagadorSerializer only exposes alumnos_count,
            # not a filtered list — the count intentionally includes any
            # siblings in the other marca too).
            qs = qs.filter(alumnos__marca=scope).distinct()
        return qs

    def perform_create(self, serializer):
        serializer.save(academia=self.request.user.tenant)


class PagadorCalculadoraView(APIView):
    """"Quién tiene que pagar cuánto, por qué y a quién, y si ya pagó y
    tiene factura/recibo" — por pagador, para el período indicado
    (?periodo=YYYY-MM, por defecto el mes actual). Deliberadamente separada
    de PagadorViewSet (que bloquea a recepción por completo y expone
    NIF/IBAN/notas): esta vista solo devuelve el nombre del pagador y lo
    que debe, así que la puede usar cualquier rol, recepción incluida.

    La cuota de cada hijo se calcula con tarifas.pricing.calcular_cuota_alumno
    — la misma función que usa la ficha del alumno, así que respeta la
    cuota manual cargada ahí sin reimplementar nada. "Por qué" es el
    desglose por hijo (tipo de cuota); el estado de pago y de
    factura/recibo se leen de los Pago de ese período.

    No cubre clases particulares para adultos (35€/hora, es_adulto=True) ni
    alumnos sin horario asignado en el sistema — esos casos salen listados
    en "avisos" para calcularlos a mano.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tenant = request.user.tenant
        scope = marca_scope_for(request.user)
        periodo = (request.query_params.get("periodo") or "").strip() or timezone.now().strftime("%Y-%m")

        pagadores_qs = Pagador.objects.filter(academia=tenant).prefetch_related(
            "alumnos__inscripciones__grupo"
        )

        resultado = []
        for pagador in pagadores_qs:
            alumnos = [a for a in pagador.alumnos.all() if a.activo and not a.es_adulto]
            if scope:
                alumnos = [a for a in alumnos if a.marca == scope]
            if not alumnos:
                continue

            avisos = []
            items = []
            total = Decimal("0")

            for alumno in alumnos:
                info = calcular_cuota_alumno(alumno)
                avisos.extend(f"{alumno.nombre}: {a}" for a in info["avisos"])
                if info["cuota"] is not None:
                    total += Decimal(str(info["cuota"]))
                items.append({
                    "tipo": info["tipo"],
                    "alumno": alumno.nombre,
                    "cuota": info["cuota"],
                })
                if info["ranger_express"] is not None:
                    total += Decimal(str(info["ranger_express"]))
                    items.append({
                        "tipo": "ranger_express",
                        "alumno": alumno.nombre,
                        "cuota": info["ranger_express"],
                    })

            pagos_periodo = list(
                Pago.objects.filter(academia=tenant, alumno_id__in=[a.id for a in alumnos], periodo=periodo)
            )
            if not pagos_periodo:
                estado_pago = "sin_generar"
            elif all(p.estado == "pagado" for p in pagos_periodo):
                estado_pago = "pagado"
            elif any(p.estado in ("pagado", "parcial") for p in pagos_periodo):
                estado_pago = "parcial"
            else:
                estado_pago = "pendiente"

            def _doc_emitido(p):
                # Mismo criterio que Pago.documento_anulado: el documento más
                # reciente (pago.documentos, o pagos_adicionales si es un pago
                # "secundario" de una factura combinada) es el que manda.
                docs = list(p.documentos.all()) or list(p.documentos_combinados.all())
                return bool(docs) and docs[0].estado == "emitida"

            documento_generado = bool(pagos_periodo) and all(_doc_emitido(p) for p in pagos_periodo)

            resultado.append({
                "pagador_id": pagador.id,
                "pagador_nombre": pagador.nombre,
                "items": items,
                "cuota_mensual_estimada": float(total),
                "avisos": avisos,
                "periodo": periodo,
                "estado_pago": estado_pago,
                "documento_generado": documento_generado,
            })

        resultado.sort(key=lambda r: r["pagador_nombre"])
        return Response(resultado)
