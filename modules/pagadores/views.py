from decimal import Decimal

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import NotReception, marca_scope_for
from modules.core.mixins import ContactableViaPagadorMixin
from modules.tarifas.pricing import (
    cuota_bono_familia, cuota_ranger_express, perfil_semanal_alumno, precio_clase_grupo,
)
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
    """"Cuánto le toca pagar" por pagador, según la guía de precios
    2026/2027. Deliberadamente separada de PagadorViewSet (que bloquea a
    recepción por completo y expone NIF/IBAN/notas): esta vista solo
    devuelve el nombre del pagador y la cuota calculada, así que la puede
    usar cualquier rol, recepción incluida.

    No cubre clases particulares para adultos (35€/hora, es_adulto=True) ni
    alumnos sin horario asignado en el sistema — esos casos salen listados
    en "avisos" para calcularlos a mano.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tenant = request.user.tenant
        scope = marca_scope_for(request.user)

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

            perfiles = [
                {"alumno": a, **dict(zip(("dias", "duracion", "aviso"), perfil_semanal_alumno(a)))}
                for a in alumnos
            ]
            avisos = [f"{p['alumno'].nombre}: {p['aviso']}" for p in perfiles if p["aviso"]]
            items = []
            total = Decimal("0")

            n_hermanos = len(perfiles)
            # Bono Familia con la tabla fija de la tarifa: solo 2 hermanos
            # con los mismos días y duración (ver tarifas.pricing.cuota_bono_familia).
            # Cualquier otro caso de hermanos no está en la tarifa: se calcula a
            # mano y aquí solo sale el aviso, sin una estimación que el cliente
            # no haya visto en el PDF.
            if n_hermanos >= 2:
                info, avisos_bono = cuota_bono_familia([p["alumno"] for p in perfiles])
                avisos.extend(a for a in avisos_bono if a not in avisos)
                if info:
                    total += info["total"]
                    items.append({
                        "tipo": "bono_familia",
                        "alumnos": [p["alumno"].nombre for p in perfiles],
                        "n_hermanos": n_hermanos,
                        "perfiles": [
                            {
                                "alumno": p["alumno"].nombre, "dias_semana": p["dias"], "duracion_min": p["duracion"],
                                "cuota": float(info["cuotas_por_hermano"][p["alumno"]]),
                            }
                            for p in perfiles
                        ],
                        "precio": float(info["total"]),
                    })
            else:
                for p in perfiles:
                    if p["duracion"] is None:
                        continue  # ya está en avisos
                    precio = precio_clase_grupo(p["dias"], p["duracion"])
                    if precio is None:
                        avisos.append(
                            f"{p['alumno'].nombre}: {p['dias']} días/sem a {p['duracion']} min "
                            "no está en la tarifa — calcular a mano."
                        )
                        continue
                    total += Decimal(precio)
                    items.append({
                        "tipo": "clase_grupo",
                        "alumnos": [p["alumno"].nombre],
                        "dias_semana": p["dias"], "duracion_min": p["duracion"],
                        "precio": precio,
                    })

            # The Ranger Express: línea fija y separada, 10€ por cada hijo
            # con el servicio — nunca entra en la suma del 5% de Bono
            # Familia (eso solo aplica a Clases Grupo), se suma después.
            alumnos_express = [a for a in alumnos if a.ranger_express]
            if alumnos_express:
                total_express = sum(Decimal(str(a.recogida_precio)) for a in alumnos_express)
                total += total_express
                items.append({
                    "tipo": "ranger_express",
                    "alumnos": [a.nombre for a in alumnos_express],
                    "precio": float(total_express),
                })

            resultado.append({
                "pagador_id": pagador.id,
                "pagador_nombre": pagador.nombre,
                "items": items,
                "cuota_mensual_estimada": float(total),
                "avisos": avisos,
            })

        resultado.sort(key=lambda r: r["pagador_nombre"])
        return Response(resultado)
