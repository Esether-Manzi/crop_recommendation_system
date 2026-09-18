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

    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
        blank=True,
        null=True,
        help_text="Shown on your profile and in the navbar.",
    )

    def save(self, *args, **kwargs):
        # createsuperuser doesn't know about this custom field, so it
        # would otherwise silently leave superusers at the default
        # Farmer role.
        if self.is_superuser and self.role != self.Role.ADMIN:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
