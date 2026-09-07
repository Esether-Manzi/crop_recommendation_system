from django.contrib import admin
from .models import Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "farm",
        "predicted_crop",
        "nitrogen",
        "phosphorus",
        "potassium",
        "ph",
        "created_at",
    )

    list_filter = (
        "predicted_crop",
        "created_at",
    )

    search_fields = (
        "user__username",
        "farm__farm_name",
        "predicted_crop",
    )
