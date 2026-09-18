"""Fixed 2026/2027 Rangers Academy group pricing, as agreed with Cami
2026-09 (same numbers as "Guía interna de precios — Curso 2026/2027").

The 60-min column matches the official pricing poster Cande already sent to
families, not a raw application of the 0/3/5/7/9% (Grupo) / flat 5%
(Familia) formula — Cande rounded those results to the nearest 5€. The
90-min column happens to need no rounding (its formula results already land
on multiples of 5€), so it's unchanged either way.

Deliberately NOT modeled through modules.tarifas.Tarifa — that model is a
flat per-tariff price lookup (nombre + horas_semanales up to 3) and doesn't
capture a per-día-de-la-semana tier (1-5) crossed with session duration
(1h / 90min), which is the actual shape of these rates. Rather than reshape
Tarifa (used elsewhere, migration risk) this lives as an explicit table.
Update this file *and* the Word guide together if prices change for a new
course year — there's no other source of truth to keep in sync with.
"""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

MATRICULA = 20  # one-off enrollment fee, per student, aparte de la cuota
PRECIO_CLASE_PRIVADA_HORA = 35  # adult 1:1 professional classes, per hour

# {duracion_min: {dias_semana: (precio_mes, descuento_pct)}}
CLASES_GRUPO = {
    60: {1: (50, 0), 2: (95, 3), 3: (145, 5), 4: (185, 7), 5: (230, 9)},
    90: {1: (72, 0), 2: (140, 3), 3: (205, 5), 4: (268, 7), 5: (328, 9)},
}

# Bono Familia = Clases Grupo x n_hermanos con un 5% de descuento fijo de
# familia, igual en todos los tramos. {n_hermanos: {duracion_min: {dias_semana: (precio_mes, descuento_pct)}}}
BONO_FAMILIA = {
    2: {
        60: {1: (95, 5), 2: (180, 5), 3: (275, 5), 4: (350, 5), 5: (435, 5)},
        90: {1: (137, 5), 2: (266, 5), 3: (390, 5), 4: (509, 5), 5: (623, 5)},
    },
    3: {
        60: {1: (145, 5), 2: (270, 5), 3: (415, 5), 4: (525, 5), 5: (655, 5)},
        90: {1: (205, 5), 2: (399, 5), 3: (584, 5), 4: (764, 5), 5: (935, 5)},
    },
    4: {
        60: {1: (190, 5), 2: (360, 5), 3: (550, 5), 4: (705, 5), 5: (875, 5)},
        90: {1: (274, 5), 2: (532, 5), 3: (779, 5), 4: (1018, 5), 5: (1246, 5)},
    },
}


def precio_clase_grupo(dias_semana, duracion_min):
    """(precio, descuento_pct) or None if that combination isn't in the
    finalized table (e.g. 0 or >5 días/semana, or a duration other than
    60/90 min)."""
    tabla = CLASES_GRUPO.get(duracion_min)
    return tabla.get(dias_semana) if tabla else None


def precio_bono_familia(dias_semana, duracion_min, n_hermanos=2):
    tabla = BONO_FAMILIA.get(n_hermanos, {}).get(duracion_min)
    return tabla.get(dias_semana) if tabla else None


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


def _redondear_5(valor):
    """Redondea a los 5€ más cercanos — misma convención que las tablas de
    BONO_FAMILIA (ya redondeadas a mano por Cande)."""
    valor = Decimal(str(valor))
    return (valor / 5).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 5


def cuota_bono_familia_prorrateada(alumnos_hermanos):
    """Regla confirmada 2026-09-19: se suman los precios individuales de
    Clase Grupo de cada hermano según su propio tramo de días/semana, se
    aplica el 5% de descuento familiar sobre la suma, se redondea a los 5€
    más cercanos, y ese total se reparte en PARTES IGUALES entre los
    hermanos — sin importar que alguno vaya a más horas/semana o con otra
    profesora (ver claude/cuota-mensual-y-clase-refuerzo-2026-09-18.md §3.1).

    Returns (info, avisos). info is None if any hermano's profile is
    missing/ambiguous or off-table — the caller should fall back to
    "cuota manual" in that case; avisos explains why."""
    perfiles = [(a, perfil_semanal_alumno(a)) for a in alumnos_hermanos]
    avisos = []
    suma = Decimal("0")
    for alumno, (dias, duracion, aviso) in perfiles:
        if aviso or duracion is None:
            avisos.append(f"{alumno.nombre}: {aviso or 'sin horario asignado'}")
            continue
        encontrado = precio_clase_grupo(dias, duracion)
        if not encontrado:
            avisos.append(f"{alumno.nombre}: {dias} días/sem a {duracion} min no está en la tabla.")
            continue
        precio, _ = encontrado
        suma += Decimal(str(precio))

    if avisos:
        return None, avisos

    total = _redondear_5(suma * Decimal("0.95"))
    n_hermanos = len(alumnos_hermanos)
    cuota_por_hermano = (total / n_hermanos).quantize(Decimal("0.01"))
    return {"cuota_por_hermano": cuota_por_hermano, "total": total, "n_hermanos": n_hermanos}, avisos


def calcular_cuota_alumno(alumno):
    """Cuota mensual automática para la ficha del alumno (AlumnoDetailPage).
    Nunca lanza — cualquier caso no cubierto vuelve con cuota=None y un
    aviso explicando por qué (para que el frontend muestre "precio manual").

    Orden: precio manual cargado > clase privada (sin fórmula) > Bono
    Familia prorrateado (2-4 hermanos activos no-adultos con el mismo
    pagador) > Clase Grupo individual > sin tabla."""
    if alumno.cuota_manual is not None:
        return {"tipo": "manual", "cuota": float(alumno.cuota_manual), "avisos": []}

    if alumno.codigo_clase in ("PRIVADA", "PRIVADA_PROFESIONAL"):
        tarifa_hora = PRECIO_CLASE_PRIVADA_HORA if alumno.codigo_clase == "PRIVADA_PROFESIONAL" else 30
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

    if len(hermanos) in (2, 3, 4):
        info, avisos = cuota_bono_familia_prorrateada(hermanos)
        if info:
            return {
                "tipo": "bono_familia", "cuota": float(info["cuota_por_hermano"]),
                "total_bono": float(info["total"]), "n_hermanos": info["n_hermanos"],
                "dias_semana": dias, "duracion_min": duracion, "avisos": avisos,
            }
        return {
            "tipo": "sin_tabla", "cuota": None,
            "dias_semana": dias, "duracion_min": duracion, "avisos": avisos,
        }

    encontrado = precio_clase_grupo(dias, duracion)
    if not encontrado:
        return {
            "tipo": "sin_tabla", "cuota": None, "dias_semana": dias, "duracion_min": duracion,
            "avisos": [f"{dias} días/sem a {duracion} min no está en la tabla — calcular a mano."],
        }
    precio, descuento = encontrado
    return {
        "tipo": "clase_grupo", "cuota": float(precio), "descuento_pct": descuento,
        "dias_semana": dias, "duracion_min": duracion, "avisos": [],
    }
