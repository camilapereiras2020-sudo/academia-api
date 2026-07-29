from datetime import date

from django.db import migrations, models


def seed_counters(apps, schema_editor):
    """Seed factura_counter/recibo_counter from the current max issued
    number per Emisor+tipo (same scan the old _next_invoice_number used),
    so switching to the atomic counter doesn't reissue a number that's
    already out there. Only looks at *this* calendar year's suffix, matching
    the old suffix-filtered scan's (and the new counter's) yearly reset.
    """
    Emisor    = apps.get_model("documentos", "Emisor")
    Documento = apps.get_model("documentos", "Documento")
    Pago      = apps.get_model("pagos", "Pago")

    year   = date.today().year
    suffix = f"-{str(year)[2:]}"

    for emisor in Emisor.objects.all():
        for prefix, baseline, counter_field, year_field in (
            (emisor.factura_prefix, emisor.factura_baseline,
             "factura_counter", "factura_counter_year"),
            (emisor.recibo_prefix, emisor.recibo_baseline,
             "recibo_counter", "recibo_counter_year"),
        ):
            max_num = baseline

            def _filters(field, prefix=prefix):
                f = {f"{field}__endswith": suffix}
                if prefix:
                    f[f"{field}__startswith"] = prefix
                return f

            for qs in (
                Documento.objects.filter(academia_id=emisor.academia_id, **_filters("num_doc"))
                    .values_list("num_doc", flat=True),
                Pago.objects.filter(academia_id=emisor.academia_id, **_filters("num_doc"))
                    .values_list("num_doc", flat=True),
                Pago.objects.filter(academia_id=emisor.academia_id, **_filters("numero_factura_reservado"))
                    .values_list("numero_factura_reservado", flat=True),
            ):
                for num_doc in qs:
                    try:
                        middle  = num_doc[len(prefix):-len(suffix)] if suffix else num_doc[len(prefix):]
                        max_num = max(max_num, int(middle))
                    except (ValueError, IndexError):
                        continue

            setattr(emisor, counter_field, max_num)
            setattr(emisor, year_field, year)

        emisor.save(update_fields=[
            "factura_counter", "factura_counter_year",
            "recibo_counter", "recibo_counter_year",
        ])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('documentos', '0007_alter_documento_pago'),
        ('pagos', '0009_concepto_alias'),
    ]

    operations = [
        migrations.AddField(
            model_name='emisor',
            name='factura_counter',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='emisor',
            name='factura_counter_year',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='emisor',
            name='recibo_counter',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='emisor',
            name='recibo_counter_year',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(seed_counters, noop_reverse),
    ]
