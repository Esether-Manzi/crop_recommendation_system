from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Custom user model that extends the default Django User model.
    """

    class Role(models.TextChoices):
        FARMER = "farmer", "Farmer"
        OFFICER = "officer", "Extension Officer"
        ADMIN = "admin", "Administrator"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.FARMER,
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
