from django.db import migrations

MOTIVO = (
    "Migrado automáticamente: su documento se anuló antes de poder decidir si el dinero "
    "se cobró. Revísalo y restaura el cobro si sí se cobró."
)


def migrar(apps, schema_editor):
    """Pagos "pagado" cuyo documento vigente más reciente está anulado pasan a
    "anulado": hasta ahora solo dos pantallas los descontaban, el resto los
    seguía sumando. Así los totales no cambian en las pantallas y quedan
    marcados para revisarlos (se pueden restaurar o borrar)."""
    Pago = apps.get_model("pagos", "Pago")
    for pago in Pago.objects.filter(estado="pagado"):
        docs = list(pago.documentos.all()) or list(pago.documentos_combinados.all())
        docs = [d for d in docs if d.estado not in ("borrador", "cuarentena")]
        if not docs:
            continue
        docs.sort(key=lambda d: (d.created_at, d.id), reverse=True)
        if docs[0].estado == "anulada":
            pago.estado = "anulado"
            pago.anulado_at = docs[0].anulada_at
            pago.motivo_anulacion = MOTIVO
            pago.save(update_fields=["estado", "anulado_at", "motivo_anulacion"])


class Migration(migrations.Migration):
    dependencies = [
        ("pagos", "0010_cobro_anulado_y_borrado"),
        ("documentos", "0012_documento_emisor"),
    ]
    operations = [migrations.RunPython(migrar, migrations.RunPython.noop)]
