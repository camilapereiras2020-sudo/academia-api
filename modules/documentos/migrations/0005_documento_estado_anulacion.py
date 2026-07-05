from django.db import migrations, models


def backfill_estado(apps, schema_editor):
    Documento = apps.get_model("documentos", "Documento")
    # Every existing row was created through a flow that already tried to issue
    # it (see fix_legacy_docs.py's philosophy of repairing, not discarding,
    # rows with a missing s3_key) — none are real untouched drafts. Classifying
    # them all as emitida (not borrador) is what keeps them permanently
    # non-hard-deletable going forward.
    Documento.objects.update(estado="emitida", emitida_at=models.F("created_at"))


class Migration(migrations.Migration):

    dependencies = [
        ("documentos", "0004_emisor_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="documento",
            name="estado",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("borrador", "Borrador"),
                    ("emitida", "Emitida"),
                    ("anulada", "Anulada"),
                    ("rectificada", "Rectificada"),
                ],
                default="borrador",
            ),
        ),
        migrations.AddField(
            model_name="documento",
            name="emitida_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="documento",
            name="anulada_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="documento",
            name="motivo_anulacion",
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(backfill_estado, migrations.RunPython.noop),
    ]
