from django.contrib import admin
from .models import RotationPlan, RotationStep

@admin.register(RotationPlan)
class RotationPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "farm", "created_at")
    list_filter = ("created_at", "farm__district")
    search_fields = ("farm__farm_name", "farm__user__username")
    date_hierarchy = "created_at"


@admin.register(RotationStep)
class RotationStepAdmin(admin.ModelAdmin):
    list_display = (
        "plan",
        "season_number",
        "crop_recommended",
        "crop_family",
        "fertilizer_applied",
        "nitrogen_before",
        "nitrogen_after",
    )
    list_filter = (
        "crop_recommended",
        "crop_family",
        "fertilizer_applied",
    )
    search_fields = ("plan__farm__farm_name", "crop_recommended", "crop_family")
