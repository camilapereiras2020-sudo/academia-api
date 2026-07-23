from datetime import date


def alumnos_con_cumpleanos_proximos(queryset, dias=30):
    """Shared by AlumnoViewSet.cumpleanos and the reception dashboard summary:
    walks the given Alumno queryset and returns those with a birthday within
    the next `dias` days, sorted soonest-first."""
    today = date.today()
    upcoming = []
    for alumno in queryset:
        if alumno.fecha_nacimiento:
            bd = alumno.fecha_nacimiento.replace(year=today.year)
            if bd < today:
                bd = bd.replace(year=today.year + 1)
            days = (bd - today).days
            if days <= dias:
                upcoming.append({
                    "id": alumno.id,
                    "nombre": alumno.nombre,
                    "fecha_nacimiento": alumno.fecha_nacimiento,
                    "dias_para_cumpleanos": days,
                })
    return sorted(upcoming, key=lambda x: x["dias_para_cumpleanos"])

