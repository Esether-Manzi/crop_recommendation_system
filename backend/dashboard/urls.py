"""
URL configuration for the Dashboard app.

Currently it only serves the home page.
Later it will contain the farmer dashboard.
"""



from django.urls import path

from . import views

app_name = "dashboard"

"""
URL configuration for the Dashboard app.
"""
urlpatterns = [
    

    # Landing Page
    path("", views.dashboard_home, name="home"),
]
