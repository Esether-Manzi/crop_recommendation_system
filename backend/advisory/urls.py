from django.urls import path
from . import views

app_name = "advisory"

urlpatterns = [
    path("", views.advisory_list, name="list"),
    path("tracker/", views.season_tracker, name="tracker"),
]
