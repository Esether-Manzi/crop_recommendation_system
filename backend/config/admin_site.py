"""
Customizes the default Django admin site: branding (header/title)
and a stats + activity overview injected into the admin index page.

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
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        pred_last_7 = Prediction.objects.filter(created_at__gte=week_ago).count()
        pred_prev_7 = Prediction.objects.filter(
            created_at__gte=two_weeks_ago, created_at__lt=week_ago
        ).count()
        if pred_prev_7:
            pred_delta = round((pred_last_7 - pred_prev_7) / pred_prev_7 * 100)
        else:
            pred_delta = 100 if pred_last_7 else 0

        new_farmers_7 = User.objects.filter(
            role=User.Role.FARMER, date_joined__gte=week_ago
        ).count()

        extra_context["dashboard_stats"] = [
            {
                "label": "Farmers",
                "value": User.objects.filter(role=User.Role.FARMER).count(),
                "icon": "fa-users",
                "trend": f"+{new_farmers_7} this week" if new_farmers_7 else "No new sign-ups",
                "trend_dir": "up" if new_farmers_7 else "flat",
            },
            {
                "label": "Farms Registered",
                "value": Farm.objects.count(),
                "icon": "fa-tractor",
                "trend": f"{Farm.objects.values('district').distinct().count()} districts",
                "trend_dir": "flat",
            },
            {
                "label": "Predictions (7 days)",
                "value": pred_last_7,
                "icon": "fa-chart-line",
                "trend": f"{'+' if pred_delta >= 0 else ''}{pred_delta}% vs prior week",
                "trend_dir": "up" if pred_delta > 0 else ("down" if pred_delta < 0 else "flat"),
            },
            {
                "label": "Predictions (all time)",
                "value": Prediction.objects.count(),
                "icon": "fa-seedling",
                "trend": "Model inferences served",
                "trend_dir": "flat",
            },
            {
                "label": "Active Seasons",
                "value": SeasonTracker.objects.filter(status="Active").count(),
                "icon": "fa-calendar-check",
                "trend": f"{SeasonTracker.objects.count()} tracked in total",
                "trend_dir": "flat",
            },
            {
                "label": "Harvest Reports",
                "value": HarvestFeedback.objects.count(),
                "icon": "fa-clipboard-check",
                "trend": "Feeding the soil model",
                "trend_dir": "flat",
            },
        ]

        # Predictions per day for the last 14 days (activity chart).
        # Range comparisons rather than __date to stay correct on MySQL
        # installs without the timezone tables loaded.
        labels, counts = [], []
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for offset in range(13, -1, -1):
            day_start = today_start - timedelta(days=offset)
            day_end = day_start + timedelta(days=1)
            labels.append(day_start.strftime("%b %d"))
            counts.append(
                Prediction.objects.filter(
                    created_at__gte=day_start, created_at__lt=day_end
                ).count()
            )
        extra_context["chart_labels"] = labels
        extra_context["chart_counts"] = counts

        extra_context["recent_predictions"] = (
            Prediction.objects.select_related("user").all()[:8]
        )

        return super().index(request, extra_context)


admin.site.__class__ = CropAIAdminSite
