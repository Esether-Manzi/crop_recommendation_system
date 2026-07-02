"""
Views for the Dashboard application.
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def dashboard_home(request):
    """
    Display the dashboard for authenticated users.

    The @login_required decorator ensures that only
    logged-in users can access this page.
    """
    return render(request, "dashboard/home.html")
