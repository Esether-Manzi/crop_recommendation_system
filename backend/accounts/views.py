"""
Views for the Accounts application.

This module handles user authentication,
registration, login, and logout.
"""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

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
    Authenticate a user and display the login page.
    """

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Welcome back!")
            return redirect("dashboard:home")

        messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html")


def logout_view(request):
    """
    Log the current user out.

    Django automatically clears the user's
    authenticated session.
    """

    logout(request)

    return redirect("dashboard:home")
