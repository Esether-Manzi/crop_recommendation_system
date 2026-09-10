from django.contrib import admin
from .models import Farm, SoilRecord

@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = (
        "farm_name",
        "user",
        "district",
        "subcounty",
        "size_acres",
        "soil_type",
        "created_at",
    )
    list_filter = (
        "soil_type",
        "district",
        "created_at",
    )
    search_fields = (
        "farm_name",
        "user__username",
        "user__email",
        "district",
        "subcounty",
    )
    raw_id_fields = ("user",)


@admin.register(SoilRecord)
class SoilRecordAdmin(admin.ModelAdmin):
    list_display = (
        "farm",
        "recorded_at",
        "nitrogen",
        "phosphorus",
        "potassium",
        "ph",
        "temperature",
        "humidity",
        "rainfall",
    )
    list_filter = (
        "recorded_at",
        "farm__district",
        "farm__soil_type",
    )
    search_fields = ("farm__farm_name", "farm__user__username")
    raw_id_fields = ("farm",)
