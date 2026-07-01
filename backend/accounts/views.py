"""
Views for the Accounts application.

This module handles user authentication,
registration, login, and logout.
"""

# Django authentication functions
from django.contrib.auth import login, logout

# Shortcut for rendering templates
from django.shortcuts import redirect, render

# Import the custom registration form
from .forms import UserRegistrationForm


def register_view(request):
    """
    Handle user registration.

    - Display the registration form (GET request)
    - Validate and save a new user (POST request)
    - Log the user in automatically after successful registration
    """

    # If the user submitted the registration form
    if request.method == "POST":

        # Populate the form with submitted data
        form = UserRegistrationForm(request.POST)

        # Check whether all fields are valid
        if form.is_valid():

            # Save the new user to the database
            user = form.save()

            # Automatically log in the newly registered user
            login(request, user)

            # Redirect to the dashboard/home page
            return redirect("dashboard:home")

    else:
        # Create an empty form for first-time visitors
        form = UserRegistrationForm()

    # Render the registration template
    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
        },
    )


def login_view(request):
    """
    Display the login page.

    Later we shall authenticate users using
    Django's authentication system.
    """

    return render(
        request,
        "accounts/login.html",
    )


def logout_view(request):
    """
    Log the current user out.

    Django automatically clears the user's
    authenticated session.
    """

    logout(request)

    return redirect("dashboard:home")
