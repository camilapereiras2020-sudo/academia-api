from django.contrib.auth.models import AbstractUser
from django.db import models

ROLE_CHOICES = [
    ("owner", "Owner"),
    ("co_manager", "Co-manager"),
    ("reception", "Reception"),
]

# Duplicated from modules.tarifas.models.MARCA_CHOICES (the canonical source used by
# Alumno/Pago/Grupo/Lead/Tarifa) rather than imported — importing it here would make
# authentication.models depend on tarifas.models, which itself calls get_user_model()
# at import time and would create a circular dependency with this, the AUTH_USER_MODEL
# app. Kept in sync by hand; the two rarely change.
MARCA_CHOICES = [
    ("cami_and_co", "Cami & Co"),
    ("rangers_academy", "Rangers Academy"),
]


class User(AbstractUser):
    email = models.EmailField(unique=True)
    academia_nombre = models.CharField(max_length=200, blank=True)
    academia_nif = models.CharField(max_length=20, blank=True)
    academia_dir = models.CharField(max_length=300, blank=True)
    academia_tel = models.CharField(max_length=20, blank=True)
    academia_logo = models.CharField(max_length=500, blank=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default="owner")
    academia_owner = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="staff_accounts"
    )
    # Only meaningful for role="co_manager" — which single marca that co-manager
    # is scoped to. Null for owner (sees everything) and reception (sees both).
    marca_asignada = models.CharField(max_length=20, choices=MARCA_CHOICES, null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.email

    @property
    def tenant(self):
        """The User whose data this account operates on — itself for an
        owner, or the owner it was delegated from for co_manager/reception
        accounts."""
        return self.academia_owner or self
