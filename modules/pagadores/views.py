from decimal import Decimal

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import NotReception, marca_scope_for
from modules.core.mixins import ContactableViaPagadorMixin
from modules.tarifas.pricing import (
    cuota_bono_familia_prorrateada, perfil_semanal_alumno, precio_clase_grupo,
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
            # Bono Familia se activa para 2-4 hermanos con perfil válido,
            # sin exigir que coincidan en días/semana o duración — se
            # reparte EN PROPORCIÓN al tramo individual de cada hermano
            # dentro de la suma, no en partes iguales (regla corregida
            # 2026-09-19, ver tarifas.pricing.cuota_bono_familia_prorrateada).
            es_bono_familia = n_hermanos in (2, 3, 4) and all(p["duracion"] is not None for p in perfiles)

            if es_bono_familia:
                info, avisos_bono = cuota_bono_familia_prorrateada([p["alumno"] for p in perfiles])
                avisos.extend(avisos_bono)
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
                    encontrado = precio_clase_grupo(p["dias"], p["duracion"])
                    if not encontrado:
                        avisos.append(
                            f"{p['alumno'].nombre}: {p['dias']} días/sem a {p['duracion']} min "
                            "no está en la tabla — calcular a mano."
                        )
                        continue
                    precio, descuento = encontrado
                    total += Decimal(str(precio))
                    items.append({
                        "tipo": "clase_grupo",
                        "alumnos": [p["alumno"].nombre],
                        "dias_semana": p["dias"], "duracion_min": p["duracion"],
                        "precio": precio, "descuento_pct": descuento,
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
