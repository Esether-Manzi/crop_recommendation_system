from django.contrib import admin
from .models import CropAdvisory, SeasonTracker

@admin.register(CropAdvisory)
class CropAdvisoryAdmin(admin.ModelAdmin):
    list_display = ("crop_name", "stage", "title")
    list_filter = ("crop_name", "stage")
    search_fields = ("crop_name", "title", "description")


@admin.register(SeasonTracker)
class SeasonTrackerAdmin(admin.ModelAdmin):
    list_display = ("farm", "crop_name", "start_date", "status")
    list_filter = ("status", "crop_name", "start_date")
    search_fields = ("farm__farm_name", "crop_name")
    date_hierarchy = "start_date"
