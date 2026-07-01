"""
Create the initial superuser from env vars if none exists.
Idempotent: does nothing if a user already exists.

Required env vars:
  DJANGO_SUPERUSER_EMAIL
  DJANGO_SUPERUSER_PASSWORD
  DJANGO_SUPERUSER_USERNAME
"""
import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Create the initial superuser from env vars if no user exists"

    def handle(self, *args, **options):
        if User.objects.exists():
            self.stdout.write("ensure_superuser: user already exists, skipping.")
            return

        email    = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")

        if not email or not password:
            self.stdout.write(self.style.ERROR(
                "ensure_superuser: DJANGO_SUPERUSER_EMAIL or DJANGO_SUPERUSER_PASSWORD not set — skipping."
            ))
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(
            f"ensure_superuser: created superuser {email} (username={username})"
        ))
