from django.contrib import admin
from .models import Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "predicted_crop",
        "created_at",
    )

    list_filter = (
        "predicted_crop",
        "created_at",
    )

    search_fields = (
        "user__username",
        "predicted_crop",
    )
