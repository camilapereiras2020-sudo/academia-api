import logging
import os
from datetime import date

from django.core.management.base import BaseCommand

from modules.alumnos.models import Alumno

logger = logging.getLogger(__name__)


def _send_birthday_email(to_email, nombre, es_alumno_directo, academia_nombre="Rangers Academy"):
    """Same Resend pattern already used and proven in
    pagos/views.py:_send_payment_email — same env vars, same gating checks.

    es_alumno_directo distinguishes who's actually reading the inbox: True
    means the email goes to the student's own address and can address them
    directly ("¡Feliz cumpleaños!"); False means it's landing in the
    pagador's (parent's) inbox as a fallback because the student has no
    email on file, so it's phrased as a heads-up about their kid instead.
    """
    from django.conf import settings
    import resend

    if os.environ.get("EMAIL_SENDING_ENABLED", "false").lower() != "true":
        logger.info("EMAIL_SENDING_ENABLED is off — skipping birthday email for %s", nombre)
        return False

    api_key = getattr(settings, "RESEND_API_KEY", "") or ""
    if not to_email:
        logger.warning("%s: no email on file (alumno or pagador) — birthday email not sent", nombre)
        return False
    if not api_key or api_key == "re_placeholder":
        logger.error("RESEND_API_KEY missing/placeholder — birthday email for %s not sent", nombre)
        return False

    resend.api_key = api_key

    if es_alumno_directo:
        subject = f"¡Feliz cumpleaños, {nombre}! 🎂"
        body = f"""
          <h2 style="color:#B08D57;margin:0;">¡Feliz cumpleaños, {nombre}! 🎉</h2>
          <p>Todo el equipo de {academia_nombre} te desea un día maravilloso.</p>
          <p>¡Que sigas disfrutando del inglés tanto como nosotros disfrutamos enseñándotelo!</p>
        """
    else:
        subject = f"¡Hoy es el cumpleaños de {nombre}! 🎂"
        body = f"""
          <h2 style="color:#B08D57;margin:0;">¡Hoy cumple años {nombre}! 🎉</h2>
          <p>Desde {academia_nombre} queríamos acompañar el día con un saludo especial.</p>
          <p>¡Un abrazo grande para {nombre} de parte de todo el equipo!</p>
        """

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#2D2D2D;">
      <div style="border-bottom:3px solid #B08D57;padding-bottom:12px;margin-bottom:20px;">
        {body}
      </div>
      <p style="color:#B08D57;margin-top:24px;"><strong>{academia_nombre}</strong></p>
    </div>
    """

    resend.Emails.send({
        "from": settings.DEFAULT_FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html,
    })
    return True


class Command(BaseCommand):
    help = (
        "Sends a birthday email to any alumno whose birthday (or configured lead time) "
        "matches today. Falls back to the pagador's email when the alumno has none of "
        "their own on file. Intended to run once daily via an external scheduler "
        "(Railway Cron Job)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print who would receive an email without actually sending or marking anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        today = date.today()
        sent, skipped = 0, 0

        # academia-scoped: every alumno already belongs to a tenant (User),
        # no cross-tenant leakage risk here since we're just iterating all
        # alumnos with a birthday, not exposing anything via the API.
        qs = Alumno.objects.filter(
            activo=True, fecha_nacimiento__isnull=False
        ).select_related("academia", "pagador")

        for alumno in qs:
            bd_this_year = alumno.fecha_nacimiento.replace(year=today.year)
            dias_para_cumple = (bd_this_year - today).days

            # aviso_cumple_dias = days *before* the birthday to send the
            # heads-up (default 0 = day-of).
            trigger_day = alumno.aviso_cumple_dias if alumno.aviso_cumple_dias is not None else 0
            if dias_para_cumple != trigger_day:
                continue

            if alumno.ultimo_email_cumple_enviado and alumno.ultimo_email_cumple_enviado.year == today.year:
                skipped += 1
                continue  # already sent this year (rerun-safe)

            es_alumno_directo = bool(alumno.email)
            to_email = alumno.email or (alumno.pagador.email if alumno.pagador else "")

            if not to_email:
                logger.warning(
                    "Alumno %s: no alumno email and no pagador email on file — birthday email not sent",
                    alumno.id,
                )
                skipped += 1
                continue

            if dry_run:
                via = "alumno" if es_alumno_directo else "pagador (fallback)"
                self.stdout.write(f"[dry-run] Would email {alumno.nombre} <{to_email}> via {via}")
                sent += 1
                continue

            academia_nombre = "Cami&Co" if alumno.marca == "cami_and_co" else "Rangers Academy"
            ok = _send_birthday_email(to_email, alumno.nombre, es_alumno_directo, academia_nombre)
            if ok:
                alumno.ultimo_email_cumple_enviado = today
                alumno.save(update_fields=["ultimo_email_cumple_enviado"])
                sent += 1

        self.stdout.write(self.style.SUCCESS(f"Birthday emails: {sent} sent, {skipped} skipped."))
