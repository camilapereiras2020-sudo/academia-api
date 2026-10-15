"""Tarifa oficial Rangers Academy 2026/2027 — la misma que reciben las familias.

Fuente de verdad: los PDF de precios que se entregan a los clientes
("Tarifa-Rangers-26-27.pdf" para 90 min) y la tarifa de 1 hora acordada con
dirección. Tablas fijas, sin fórmula: si cambia un precio, cambia primero en
el PDF y después aquí, en frontend/src/features/tarifas/pages/PreciosPage.tsx
y en frontend/src/features/pagadores/pages/CalculadoraPage.tsx. Los tests de
modules/tarifas/tests.py fijan estas cifras.

Excepción: Bono Familia de 3-4 hermanos, o 2 hermanos en tramos distintos,
no tiene tarifa publicada — cuota_bono_familia cae a una fórmula ESTIMADA
(_cuota_bono_familia_estimada) en vez de una tabla, y lo marca con un aviso
explícito para que no se confunda con la tarifa oficial de 2 hermanos.

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


def _redondear_5(valor):
    """Redondea a los 5€ más cercanos — mismo criterio que usa dirección
    para fijar BONO_FAMILIA en 60 min (ver _cuota_bono_familia_estimada)."""
    valor = Decimal(str(valor))
    return (valor / 5).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 5


def _cuota_bono_familia_estimada(perfiles):
    """Fallback para 3-4 hermanos, o 2 hermanos en tramos distintos — casos
    que NO están en la tabla oficial BONO_FAMILIA (esa tabla solo cubre
    exactamente 2 hermanos con el mismo tramo). No hay tarifa publicada para
    estos casos, así que se ESTIMA: se suma el precio individual
    (precio_clase_grupo) de cada hermano según su propio tramo, se aplica el
    5% de descuento familiar sobre la suma y se redondea a los 5€ más
    cercanos — el mismo cálculo que reproduce la tabla oficial en 60 min,
    pero en 90 min la tabla real trae descuentos extra negociados aparte que
    esta fórmula NO reproduce (verificado contra Tarifa-Rangers-26-27.pdf:
    90 min/1 día da 145 en vez de 130, 90 min/3 días da 380 en vez de 375).
    Por eso el aviso dice explícitamente que es una estimación a confirmar,
    nunca "tarifa oficial".

    El total se reparte en proporción al precio individual de cada
    hermano — quien va más horas paga más — ajustando el céntimo en el
    último para que la suma cierre exacta.

    Returns (info, avisos) — info is None if some sibling's profile is
    missing/off-table, igual que cuota_bono_familia."""
    precios = []
    for alumno, (dias, duracion, aviso) in perfiles:
        if aviso or duracion is None:
            return None, [f"{alumno.nombre}: {aviso or 'sin horario asignado'}"]
        precio = precio_clase_grupo(dias, duracion)
        if precio is None:
            return None, [f"{alumno.nombre}: {dias} días/sem a {duracion} min no está en la tarifa."]
        precios.append((alumno, Decimal(precio)))

    suma = sum(precio for _, precio in precios)
    total = _redondear_5(suma * Decimal("0.95"))

    cuotas_por_hermano = {}
    asignado = Decimal("0")
    for i, (alumno, precio) in enumerate(precios):
        if i < len(precios) - 1:
            parte = (total * precio / suma).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            cuotas_por_hermano[alumno] = parte
            asignado += parte
        else:
            cuotas_por_hermano[alumno] = total - asignado

    return {
        "cuotas_por_hermano": cuotas_por_hermano, "total": total, "n_hermanos": len(precios),
    }, [
        "Bono Familia ESTIMADO (no hay tarifa oficial publicada para este caso — "
        "confirmar con dirección antes de facturar)."
    ]


def cuota_bono_familia(alumnos_hermanos):
    """Bono Familia: tabla fija de la tarifa cuando aplica (2 hermanos,
    mismo tramo); fórmula estimada como fallback para 3-4 hermanos o
    tramos distintos (_cuota_bono_familia_estimada). Más de 4 hermanos, o
    cualquier perfil sin horario/fuera de tabla, sigue sin estimación.

    Returns (info, avisos). info is None when ni la tabla ni la fórmula
    cubren el caso — the caller falls back to "precio manual"; avisos
    explains why."""
    perfiles = [(a, perfil_semanal_alumno(a)) for a in alumnos_hermanos]
    avisos = [f"{a.nombre}: {aviso}" for a, (_, _, aviso) in perfiles if aviso]
    if avisos:
        return None, avisos

    n_hermanos = len(perfiles)
    if n_hermanos not in (2, 3, 4):
        return None, [f"Bono Familia de {n_hermanos} hermanos no está en la tarifa — calcular a mano."]

    if n_hermanos == BONO_FAMILIA_HERMANOS:
        combinaciones = {(dias, duracion) for _, (dias, duracion, _) in perfiles}
        if len(combinaciones) == 1:
            dias, duracion = combinaciones.pop()
            precio = precio_bono_familia(dias, duracion)
            if precio is not None:
                total = Decimal(precio)
                mitad = (total / BONO_FAMILIA_HERMANOS).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                (primero, _), (segundo, _) = perfiles
                cuotas_por_hermano = {primero: mitad, segundo: total - mitad}
                return {
                    "cuotas_por_hermano": cuotas_por_hermano, "total": total,
                    "n_hermanos": n_hermanos, "dias_semana": dias, "duracion_min": duracion,
                }, []

    # 3-4 hermanos, o 2 hermanos en tramos distintos / fuera de la tabla
    # oficial: estimar con la fórmula de reparto proporcional.
    return _cuota_bono_familia_estimada(perfiles)


def cuota_ranger_express(alumno):
    """The Ranger Express (recogida del cole): cargo fijo mensual, SEPARADO
    de la cuota de clases — nunca entra en la suma del 5% de descuento de
    Bono Familia (ese descuento solo aplica a Clases Grupo). None si el
    alumno no tiene el servicio."""
    if not alumno.ranger_express:
        return None
    return float(alumno.recogida_precio)


def calcular_cuota_alumno(alumno):
    """Cuota mensual automática para la ficha del alumno (AlumnoDetailPage):
    cuota de clase + "ranger_express" como línea aparte (ver
    cuota_ranger_express — nunca se mezcla con el prorrateo de Bono
    Familia)."""
    resultado = _calcular_cuota_clase(alumno)
    resultado["ranger_express"] = cuota_ranger_express(alumno)
    return resultado


def _calcular_cuota_clase(alumno):
    """Cuota mensual de la clase (sin Ranger Express — ver calcular_cuota_alumno).
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
