from django.db import models
from farms.models import Farm

class CropAdvisory(models.Model):
    STAGE_CHOICES = [
        ("Preparation", "Land Preparation"),
        ("Planting", "Planting & Spacing"),
        ("Fertilizer", "Nutrient & Fertilizer"),
        ("Weeding", "Weeding"),
        ("Pests", "Pest Control"),
        ("Diseases", "Disease Management"),
        ("Harvest", "Harvesting"),
        ("Storage", "Post-Harvest Storage"),
    ]

    crop_name = models.CharField(max_length=100, help_text="e.g., maize, beans, cassava")
    stage = models.CharField(max_length=50, choices=STAGE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()

    class Meta:
        verbose_name_plural = "Crop Advisories"
        unique_together = ("crop_name", "stage")

    def __str__(self):
        return f"{self.crop_name.title()} - {self.get_stage_display()}"


class SeasonTracker(models.Model):
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name="trackers"
    )
    crop_name = models.CharField(max_length=100)
    start_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=[("Active", "Active"), ("Completed", "Completed")],
        default="Active"
    )

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.crop_name.title()} on {self.farm.farm_name} ({self.status})"
