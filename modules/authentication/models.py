from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    email = models.EmailField(unique=True)
    academia_nombre = models.CharField(max_length=200, blank=True)
    academia_nif = models.CharField(max_length=20, blank=True)
    academia_dir = models.CharField(max_length=300, blank=True)
    academia_tel = models.CharField(max_length=20, blank=True)
    academia_logo = models.CharField(max_length=500, blank=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.email
