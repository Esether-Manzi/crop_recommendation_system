from django.db import models
from farms.models import Farm

class RotationPlan(models.Model):
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name="rotation_plans"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Rotation Plan for {self.farm.farm_name} ({self.created_at.strftime('%Y-%m-%d')})"


class RotationStep(models.Model):
    plan = models.ForeignKey(
        RotationPlan,
        on_delete=models.CASCADE,
        related_name="steps"
    )
    season_number = models.IntegerField()
    crop_recommended = models.CharField(max_length=100)
    crop_family = models.CharField(max_length=100, blank=True, null=True)
    fertilizer_applied = models.BooleanField(default=False)

    # Soil chemical states before growing
    nitrogen_before = models.FloatField()
    phosphorus_before = models.FloatField()
    potassium_before = models.FloatField()
    ph_before = models.FloatField()

    # Soil chemical states after growing (simulated)
    nitrogen_after = models.FloatField()
    phosphorus_after = models.FloatField()
    potassium_after = models.FloatField()
    ph_after = models.FloatField()

    class Meta:
        ordering = ["season_number"]

    def __str__(self):
        return f"Season {self.season_number} - {self.crop_recommended} ({self.plan.farm.farm_name})"
