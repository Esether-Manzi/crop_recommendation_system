"""
Forms for the Accounts application.

This module contains forms related to user
registration and authentication.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm

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

        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"