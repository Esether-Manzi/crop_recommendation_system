"""
Views for the Dashboard application.
"""

from django.shortcuts import render


def home(request):
    """
    Display the public landing page.

    Later, this page will introduce the crop
    recommendation system to visitors.
    """

    return render(
        request,
        "home/index.html",
    )
