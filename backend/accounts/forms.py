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