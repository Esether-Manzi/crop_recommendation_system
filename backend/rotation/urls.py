from django.urls import path
from . import views

app_name = "rotation"

urlpatterns = [
    path("", views.planner, name="planner"),
]
