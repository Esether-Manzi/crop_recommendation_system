from django.urls import path
from . import views

app_name = "recommendations"

urlpatterns = [
    path("predict/", views.predict_crop, name="predict_crop"),
]