"""Tarifa oficial Rangers Academy 2026/2027 — la misma que reciben las familias.

Fuente de verdad: los PDF de precios que se entregan a los clientes
("Tarifa-Rangers-26-27.pdf" para 90 min) y la tarifa de 1 hora acordada con
dirección. Tablas fijas, sin fórmula: si cambia un precio, cambia primero en
el PDF y después aquí, en frontend/src/features/tarifas/pages/PreciosPage.tsx
y en frontend/src/features/pagadores/pages/CalculadoraPage.tsx. Los tests de
modules/tarifas/tests.py fijan estas cifras.

Deliberately NOT modeled through modules.tarifas.Tarifa — that model is a
flat per-tariff price lookup and doesn't capture a per-día-de-la-semana tier
crossed with session duration (1h / 90min), which is the actual shape of
these rates.
"""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

MATRICULA = 20  # pago único por alumno, aparte de la cuota; exenta de IVA
PRECIO_CLASE_PRIVADA_HORA = 30
PRECIO_CLASE_PRIVADA_PROFESIONAL_HORA = 35  # privada profesional o especialización

# Clases Grupo, precio por alumno y mes. {duracion_min: {dias_semana: precio}}
# 90 min solo existe de 1 a 3 días/semana. No hay clases de 2 horas.
CLASES_GRUPO = {
    60: {1: 50, 2: 95, 3: 145, 4: 185, 5: 230},
    90: {1: 75, 2: 137, 3: 200},
}

# Bono Familia: precio conjunto por mes para 2 hermanos que van los mismos
# días y la misma duración. {duracion_min: {dias_semana: precio}}
BONO_FAMILIA = {
    60: {1: 95, 2: 180, 3: 275, 4: 350, 5: 435},
    90: {1: 130, 2: 260, 3: 375},
}
BONO_FAMILIA_HERMANOS = 2


def precio_clase_grupo(dias_semana, duracion_min):
    """Precio mensual de la tarifa, o None si esa combinación no está en la
    tarifa (0 o >5 días, 90 min con más de 3 días, otra duración)."""
    return CLASES_GRUPO.get(duracion_min, {}).get(dias_semana)


def precio_bono_familia(dias_semana, duracion_min):
    """Precio mensual conjunto del Bono Familia, o None si no está en la tarifa."""
    return BONO_FAMILIA.get(duracion_min, {}).get(dias_semana)


def perfil_semanal_alumno(alumno):
    """Derives (dias_semana, duracion_min, aviso) from this alumno's active
    class memberships (Inscripcion -> Grupo.horarios).

    dias_semana: total weekly sessions across every group they're enrolled
    in (sums Grupo.horarios length per membership — if a student attends two
    different classes on the same weekday this double-counts that day; edge
    case, not handled).

    duracion_min: the most common per-session length among their classes.
    aviso is set (non-empty) when there's no schedule at all, or when their
    classes mix more than one session length — either way reception should
    check that student by hand instead of trusting an averaged number.
    """
    duraciones = []
    dias_semana = 0
    for insc in alumno.inscripciones.select_related("grupo").all():
        horarios = insc.grupo.horarios or []
        dias_semana += len(horarios)
        for h in horarios:
            try:
                ini_h, ini_m = (int(x) for x in h["ini"].split(":"))
                fin_h, fin_m = (int(x) for x in h["fin"].split(":"))
                duraciones.append((fin_h * 60 + fin_m) - (ini_h * 60 + ini_m))
            except (KeyError, ValueError, AttributeError, TypeError):
                continue

    if not duraciones:
        return dias_semana, None, "sin horario asignado — no se puede calcular"

    conteo = Counter(duraciones)
    duracion_predominante, _ = conteo.most_common(1)[0]
    aviso = "" if len(conteo) == 1 else "clases de distinta duración — revisar a mano"
    return dias_semana, duracion_predominante, aviso


def cuota_bono_familia(alumnos_hermanos):
    """Bono Familia con la tabla fija de la tarifa, sin fórmula.

    Solo aplica a exactamente 2 hermanos que van los mismos días/semana y la
    misma duración: el precio sale de BONO_FAMILIA y se reparte a partes
    iguales (el céntimo sobrante, si lo hay, va al último para que la suma
    cierre exacta en el precio de la tarifa). Cualquier otro caso no está en
    la tarifa y se calcula a mano.

    Returns (info, avisos). info is None when the tarifa doesn't cover the
    case — the caller falls back to "precio manual"; avisos explains why."""
    perfiles = [(a, perfil_semanal_alumno(a)) for a in alumnos_hermanos]
    avisos = [f"{a.nombre}: {aviso}" for a, (_, _, aviso) in perfiles if aviso]
    if avisos:
        return None, avisos
    if len(perfiles) != BONO_FAMILIA_HERMANOS:
        return None, [f"Bono Familia de {len(perfiles)} hermanos no está en la tarifa — calcular a mano."]

    combinaciones = {(dias, duracion) for _, (dias, duracion, _) in perfiles}
    if len(combinaciones) != 1:
        return None, ["Bono Familia: los hermanos van distintos días o duración — calcular a mano."]
    dias, duracion = combinaciones.pop()
    precio = precio_bono_familia(dias, duracion)
    if precio is None:
        return None, [f"Bono Familia: {dias} días/sem a {duracion} min no está en la tarifa — calcular a mano."]

    total = Decimal(precio)
    mitad = (total / BONO_FAMILIA_HERMANOS).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    (primero, _), (segundo, _) = perfiles
    cuotas_por_hermano = {primero: mitad, segundo: total - mitad}
    return {
        "cuotas_por_hermano": cuotas_por_hermano, "total": total,
        "n_hermanos": BONO_FAMILIA_HERMANOS, "dias_semana": dias, "duracion_min": duracion,
    }, []


def calcular_cuota_alumno(alumno):
    """Cuota mensual automática para la ficha del alumno (AlumnoDetailPage).
    Nunca lanza — cualquier caso no cubierto vuelve con cuota=None y un
    aviso explicando por qué (para que el frontend muestre "precio manual").

    Orden: precio manual cargado > clase privada (sin fórmula) > Bono
    Familia (hermanos activos no-adultos con el mismo pagador; solo 2 con el
    mismo perfil están en la tarifa) > Clase Grupo individual > sin tabla."""
    if alumno.cuota_manual is not None:
        return {"tipo": "manual", "cuota": float(alumno.cuota_manual), "avisos": []}

    if alumno.codigo_clase in ("PRIVADA", "PRIVADA_PROFESIONAL"):
        tarifa_hora = (PRECIO_CLASE_PRIVADA_PROFESIONAL_HORA if alumno.codigo_clase == "PRIVADA_PROFESIONAL"
                       else PRECIO_CLASE_PRIVADA_HORA)
        return {
            "tipo": "privada_manual", "cuota": None, "tarifa_hora_referencia": tarifa_hora,
            "avisos": ["Clase privada: tarifa por hora, no se calcula sola — cargar precio manual."],
        }

    dias, duracion, aviso = perfil_semanal_alumno(alumno)
    if aviso or duracion is None:
        return {"tipo": "sin_tabla", "cuota": None, "avisos": [aviso or "Sin horario asignado."]}

    hermanos = []
    if alumno.pagador_id:
        hermanos = [a for a in alumno.pagador.alumnos.all() if a.activo and not a.es_adulto]

    if len(hermanos) >= 2:
        info, avisos = cuota_bono_familia(hermanos)
        if info:
            cuota_alumno = info["cuotas_por_hermano"][alumno]
            return {
                "tipo": "bono_familia", "cuota": float(cuota_alumno),
                "total_bono": float(info["total"]), "n_hermanos": info["n_hermanos"],
                "dias_semana": dias, "duracion_min": duracion, "avisos": avisos,
            }
        return {
            "tipo": "sin_tabla", "cuota": None,
            "dias_semana": dias, "duracion_min": duracion, "avisos": avisos,
        }

    precio = precio_clase_grupo(dias, duracion)
    if precio is None:
        return {
            "tipo": "sin_tabla", "cuota": None, "dias_semana": dias, "duracion_min": duracion,
            "avisos": [f"{dias} días/sem a {duracion} min no está en la tarifa — calcular a mano."],
        }
    return {
        "tipo": "clase_grupo", "cuota": float(precio),
        "dias_semana": dias, "duracion_min": duracion, "avisos": [],
    }
