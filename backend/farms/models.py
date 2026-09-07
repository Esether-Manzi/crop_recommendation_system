from django.conf import settings
from django.db import models

class Farm(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="farms"
    )
    farm_name = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    subcounty = models.CharField(max_length=100)
    size_acres = models.FloatField(help_text="Size of the farm in acres")
    soil_type = models.CharField(
        max_length=100,
        choices=[
            ("Loam", "Loam"),
            ("Sandy", "Sandy"),
            ("Clay", "Clay"),
            ("Silt", "Silt"),
            ("Peat", "Peat"),
            ("Chalky", "Chalky"),
            ("Volcanic", "Volcanic"),
        ],
        default="Loam"
    )
    latitude = models.FloatField(blank=True, null=True, help_text="GPS Latitude (optional)")
    longitude = models.FloatField(blank=True, null=True, help_text="GPS Longitude (optional)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.farm_name} ({self.district})"


class SoilRecord(models.Model):
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name="soil_records"
    )
    recorded_at = models.DateTimeField(auto_now_add=True)
    nitrogen = models.FloatField(help_text="Nitrogen (N) value in mg/kg")
    phosphorus = models.FloatField(help_text="Phosphorus (P) value in mg/kg")
    potassium = models.FloatField(help_text="Potassium (K) value in mg/kg")
    ph = models.FloatField(help_text="Soil pH level (3.5 - 8.5)")
    temperature = models.FloatField(help_text="Average temperature in °C")
    humidity = models.FloatField(help_text="Average relative humidity in %")
    rainfall = models.FloatField(help_text="Average seasonal rainfall in mm")

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"Soil Record for {self.farm.farm_name} on {self.recorded_at.strftime('%Y-%m-%d')}"
