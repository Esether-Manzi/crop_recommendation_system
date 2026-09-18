from django.urls import path

from . import views

app_name = "notes"

urlpatterns = [
    path("", views.notes_list, name="list"),
    path("<int:note_id>/edit/", views.note_edit, name="edit"),
    path("<int:note_id>/delete/", views.note_delete, name="delete"),
]
