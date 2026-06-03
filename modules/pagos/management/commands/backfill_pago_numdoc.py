from django.core.management.base import BaseCommand
from modules.documentos.models import Documento
from modules.pagos.models import Pago


class Command(BaseCommand):
    help = (
        "Sync Pago.num_doc from the most recently generated Documento for that pago. "
        "Skips pagos whose num_doc already matches. Reports duplicates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        updated = 0
        skipped = 0

        # Build a set of num_docs that are already the primary num_doc of some pago
        # (so we avoid assigning a duplicate).
        taken = set(
            Pago.objects.exclude(num_doc="").values_list("num_doc", flat=True)
        )

        # For each pago, iterate docs newest-first and pick the first num_doc
        # that isn't already taken by a different pago.
        docs_by_pago = {}
        for doc in (
            Documento.objects
            .exclude(num_doc="")
            .exclude(pago__isnull=True)
            .select_related("pago")
            .order_by("pago_id", "-created_at")
        ):
            docs_by_pago.setdefault(doc.pago_id, []).append(doc)

        for pago_id, doc_list in docs_by_pago.items():
            pago = doc_list[0].pago
            current = pago.num_doc

            # Walk newest to oldest, pick first num_doc not taken by another pago.
            chosen = None
            for doc in doc_list:
                candidate = doc.num_doc
                if candidate == current:
                    # Already correct.
                    chosen = current
                    break
                if candidate not in taken or candidate == current:
                    chosen = candidate
                    break
                self.stdout.write(
                    self.style.WARNING(
                        f"  pago {pago_id}: skipping {candidate!r} (already assigned to another pago)"
                    )
                )

            if chosen is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"  pago {pago_id}: no safe num_doc found, manual review needed"
                    )
                )
                continue

            if chosen == current:
                skipped += 1
                continue

            self.stdout.write(
                f"  pago {pago_id}: {current!r} -> {chosen!r}"
                f"  (doc created {doc_list[0].created_at:%Y-%m-%d %H:%M})"
            )

            if not dry_run:
                pago.num_doc = chosen
                pago.save(update_fields=["num_doc"])
                taken.discard(current)
                taken.add(chosen)

            updated += 1

        label = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{label}Done. {updated} pago(s) updated, {skipped} already correct."
            )
        )
