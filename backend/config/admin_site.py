"""
Customizes the default Django admin site: branding (header/title)
and a stats overview injected into the admin index page.

Imported once from config/urls.py at startup. Swaps the class of the
already-instantiated default `admin.site` in place, so every app's
existing `@admin.register(...)` calls keep working unchanged.
"""

from datetime import timedelta

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils import timezone

from accounts.models import User
from advisory.models import SeasonTracker
from farms.models import Farm
from feedback.models import HarvestFeedback
from recommendations.models import Prediction


class CropAIAdminSite(AdminSite):
    site_header = "CropAI Administration"
    site_title = "CropAI Admin"
    index_title = "Dashboard Overview"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        week_ago = timezone.now() - timedelta(days=7)

        extra_context["dashboard_stats"] = [
            {
                "label": "Farmers",
                "value": User.objects.filter(role=User.Role.FARMER).count(),
                "icon": "fa-user",
            },
            {
                "label": "Farms Registered",
                "value": Farm.objects.count(),
                "icon": "fa-tractor",
            },
            {
                "label": "Predictions (all time)",
                "value": Prediction.objects.count(),
                "icon": "fa-seedling",
            },
            {
                "label": "Predictions (last 7 days)",
                "value": Prediction.objects.filter(created_at__gte=week_ago).count(),
                "icon": "fa-chart-line",
            },
            {
                "label": "Active Seasons",
                "value": SeasonTracker.objects.filter(status="Active").count(),
                "icon": "fa-calendar-check",
            },
            {
                "label": "Harvest Reports Logged",
                "value": HarvestFeedback.objects.count(),
                "icon": "fa-clipboard-check",
            },
        ]

        return super().index(request, extra_context)


admin.site.__class__ = CropAIAdminSite
