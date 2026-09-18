"""
Forms for the Accounts application.

This module contains forms related to user
registration and authentication.
"""

from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm

from .models import User


class UserRegistrationForm(UserCreationForm):
    """
    Custom registration form.

    This extends Django's built-in UserCreationForm
    to include additional fields from our custom User model.
    """

    class Meta:
        model = User

        # Fields displayed on the registration form
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "role",
            "password1",
            "password2",
        )

    # Add Bootstrap classes to all form fields
    def __init__(self, *args, **kwargs):
        """
        Initialize the form and apply Bootstrap styling
        to every input field.
        """
        super().__init__(*args, **kwargs)

        # Administrator accounts are provisioned by an existing admin
        # (Django admin site or a management command), not self-registered.
        # Restricting the field's choices also rejects a role=admin POST
        # submitted directly, not just what the widget renders.
        self.fields["role"].choices = [
            choice for choice in self.fields["role"].choices
            if choice[0] != User.Role.ADMIN
        ]

        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class PasswordResetRequestForm(forms.Form):
    """
    Collects the email address a reset link should be sent to.

    Deliberately doesn't validate that the address belongs to an
    existing account — the view sends the same confirmation message
    either way, so this form can't be used to enumerate users.
    """

    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your registered email",
            }
        )
    )


class SetNewPasswordForm(SetPasswordForm):
    """
    Django's SetPasswordForm (new_password1/new_password2 with the
    project's AUTH_PASSWORD_VALIDATORS applied) styled with Bootstrap.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class ProfileForm(forms.ModelForm):
    """
    Lets a logged-in user update their own account details: username,
    email, phone number, and profile picture.
    """

    class Meta:
        model = User
        fields = ("profile_picture", "username", "email", "phone_number")
        widgets = {
            "profile_picture": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., 0700 000000"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"]
        if email and User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("That email is already in use by another account.")
        return email

    def clean_profile_picture(self):
        picture = self.cleaned_data.get("profile_picture")
        if picture and hasattr(picture, "size") and picture.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Please choose an image under 5MB.")
        return picture