from django.db import models
from farms.models import Farm

class HarvestFeedback(models.Model):
    YIELD_CHOICES = [
        ("Good", "Good Yield (Expected or higher)"),
        ("Average", "Average Yield"),
        ("Poor", "Poor Yield"),
        ("Failed", "Crop Failure / Minimal Yield"),
    ]

    RESIDUE_CHOICES = [
        ("Incorporated", "Incorporated back into the soil (Green manure)"),
        ("Removed", "Removed / Burned / Fed to livestock"),
    ]

    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name="feedbacks"
    )
    crop_name = models.CharField(max_length=100)
    yield_rating = models.CharField(max_length=20, choices=YIELD_CHOICES)
    satisfaction_score = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    residue_management = models.CharField(max_length=30, choices=RESIDUE_CHOICES)
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.crop_name.title()} Feedback for {self.farm.farm_name} ({self.yield_rating})"
