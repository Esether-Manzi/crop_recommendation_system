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

    # -------------------------------
    # Profile
    # -------------------------------

    path(
        "profile/",
        views.profile_view,
        name="profile",
    ),

    # -------------------------------
    # Password Reset URLs
    # -------------------------------

    # Request a reset link by email
    path(
        "password-reset/",
        views.password_reset_request_view,
        name="password_reset_request",
    ),

    # Follow the emailed link to set a new password
    path(
        "password-reset/<uidb64>/<token>/",
        views.password_reset_confirm_view,
        name="password_reset_confirm",
    ),
]