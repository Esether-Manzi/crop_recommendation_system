from django.conf import settings
from django.db import models


class Prediction(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="predictions"
    )
    farm = models.ForeignKey(
        "farms.Farm",
        on_delete=models.SET_NULL,
        related_name="predictions",
        blank=True,
        null=True,
    )

    nitrogen = models.FloatField()
    phosphorus = models.FloatField()
    potassium = models.FloatField()
    temperature = models.FloatField()
    humidity = models.FloatField()
    ph = models.FloatField()
    rainfall = models.FloatField(help_text="Annual rainfall in mm, as entered by the user")

    predicted_crop = models.CharField(max_length=100)
    model_version = models.CharField(
        max_length=40,
        blank=True,
        help_text="Version of the trained model that made this prediction (see ml/model/model_card.json).",
    )
    input_warnings = models.JSONField(
        default=list,
        blank=True,
        help_text="Warnings raised by ml/input_checks.py about the entered values.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.predicted_crop}"
