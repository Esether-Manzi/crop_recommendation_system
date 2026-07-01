"""
URL configuration for the Accounts app.

Each path defined here is responsible for handling
user authentication and account management.
"""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [

    # -------------------------------
    # Authentication URLs
    # -------------------------------

    # User Registration
    path(
        "register/",
        views.register_view,
        name="register",
    ),

    # User Login
    path(
        "login/",
        views.login_view,
        name="login",
    ),

    # User Logout
    path(
        "logout/",
        views.logout_view,
        name="logout",
    ),
]