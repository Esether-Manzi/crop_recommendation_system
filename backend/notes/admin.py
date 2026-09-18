from django.contrib import admin

from .models import Note


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "user",
        "farm",
        "updated_at",
    )
    list_filter = (
        "updated_at",
        "farm__district",
    )
    search_fields = (
        "title",
        "content",
        "user__username",
        "farm__farm_name",
    )
    raw_id_fields = ("user", "farm")
