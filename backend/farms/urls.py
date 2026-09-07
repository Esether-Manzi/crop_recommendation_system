from django.urls import path
from . import views

app_name = "farms"

urlpatterns = [
    path("", views.farms_list, name="list"),
    path("<int:farm_id>/", views.farm_detail, name="detail"),
]
