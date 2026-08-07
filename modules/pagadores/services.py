from .models import Pagador


def get_or_create_pagador(academia, nombre, telefono="", email="", direccion=""):
    """Single shared entry point for "auto-create a Pagador from a resolved
    name" logic. Deliberately generic — it takes a plain name string and
    doesn't know about Lead, Alumno, es_adulto, or pagador_es_alumno; callers
    resolve the name first. Uses get_or_create (not create) to preserve the
    existing dedup-by-name semantics: two callers resolving the same
    academia+nombre must land on the same Pagador rather than creating
    duplicates.
    """
    pagador, _ = Pagador.objects.get_or_create(
        academia=academia,
        nombre=nombre,
        defaults={
            "telefono": telefono,
            "email": email,
            "direccion": direccion,
        },
    )
    return pagador
