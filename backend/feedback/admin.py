from django.contrib import admin
from .models import HarvestFeedback

@admin.register(HarvestFeedback)
class HarvestFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "farm",
        "crop_name",
        "yield_rating",
        "satisfaction_score",
        "residue_management",
        "created_at",
    )
    list_filter = (
        "yield_rating",
        "satisfaction_score",
        "residue_management",
        "created_at",
    )
    search_fields = (
        "farm__farm_name",
        "crop_name",
        "comments",
    )
    raw_id_fields = ("farm",)
