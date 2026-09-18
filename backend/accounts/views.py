"""
Views for the Accounts application.

This module handles user authentication,
registration, login, and logout.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from .forms import PasswordResetRequestForm, ProfileForm, SetNewPasswordForm, UserRegistrationForm
from .models import User


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


def password_reset_request_view(request):
    """
    Handle a user's request to reset a forgotten password.

    Emails a signed, time-limited reset link to the address on file.
    The same confirmation message is shown whether or not the email
    matches an account, so this can't be used to enumerate users.
    """

    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]
            user = User.objects.filter(email__iexact=email).first()

            if user is not None:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_url = request.build_absolute_uri(
                    reverse("accounts:password_reset_confirm", args=[uid, token])
                )

                send_mail(
                    subject="Reset your Crop Recommendation System password",
                    message=(
                        f"Hi {user.username},\n\n"
                        "We received a request to reset your password. "
                        "Use the link below to choose a new one:\n\n"
                        f"{reset_url}\n\n"
                        "If you didn't request this, you can safely ignore this email."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                )

            messages.success(
                request,
                "If that email is registered, a password reset link has been sent to it.",
            )
            return redirect("accounts:login")

    else:
        form = PasswordResetRequestForm()

    return render(request, "accounts/password_reset_request.html", {"form": form})


def password_reset_confirm_view(request, uidb64, token):
    """
    Validate a password reset link and let the user set a new password.
    """

    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    valid_link = user is not None and default_token_generator.check_token(user, token)

    if not valid_link:
        messages.error(request, "This password reset link is invalid or has expired.")
        return redirect("accounts:password_reset_request")

    if request.method == "POST":
        form = SetNewPasswordForm(user, request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Your password has been reset. You can now log in.")
            return redirect("accounts:login")

    else:
        form = SetNewPasswordForm(user)

    return render(request, "accounts/password_reset_confirm.html", {"form": form})


@login_required
def profile_view(request):
    """
    Show and update the logged-in user's own profile: username, email,
    phone number, and profile picture.
    """

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)

        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")

        # Validating a ModelForm mutates its bound instance in place even
        # when invalid, and that instance is the same request.user object
        # the navbar/header read from — refresh it so a rejected value
        # (e.g. a username that's already taken) doesn't briefly display
        # as if it had actually been saved.
        request.user.refresh_from_db()
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "accounts/profile.html", {"form": form})


@require_POST
def logout_view(request):
    """
    Log the current user out.

    Django automatically clears the user's
    authenticated session.
    """

    logout(request)

    return redirect("dashboard:home")
