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

# Font Awesome icon per crop, for the "Latest predictions" feed — falls
# back to a generic seedling for any crop not listed here.
CROP_ICONS = {
    "rice": "fa-wheat-awn",
    "maize": "fa-wheat-awn",
    "millet": "fa-wheat-awn",
    "sorghum": "fa-wheat-awn",
    "wheat": "fa-wheat-awn",
    "orange": "fa-lemon",
    "citrus": "fa-lemon",
    "cassava": "fa-carrot",
    "sweet potato": "fa-carrot",
    "irish potato": "fa-carrot",
    "carrot": "fa-carrot",
    "coffee": "fa-mug-hot",
    "banana": "fa-apple-whole",
    "mango": "fa-apple-whole",
    "avocado": "fa-apple-whole",
    "pineapple": "fa-apple-whole",
    "beans": "fa-seedling",
    "pigeonpeas": "fa-seedling",
    "soybean": "fa-seedling",
    "groundnuts": "fa-seedling",
    "cotton": "fa-cloud",
    "jute": "fa-leaf",
}

# A small, fixed color rotation so crops without a dedicated icon are
# still visually distinct from one another in the feed.
CROP_COLORS = ["green", "gold", "teal", "terracotta", "blue"]

# Apps ordered by how often admins actually work in them; the last two
# (account/permission plumbing) are rendered de-emphasized in the
# "Manage" grid so day-to-day models aren't competing for attention.
APP_PRIORITY = ["farms", "recommendations", "rotation", "advisory", "feedback", "accounts", "auth"]
LOW_PRIORITY_APPS = {"accounts", "auth"}


def _crop_style(crop_name):
    key = (crop_name or "").strip().lower()
    icon = CROP_ICONS.get(key, "fa-seedling")
    color = CROP_COLORS[hash(key) % len(CROP_COLORS)]
    return icon, color


class CropAIAdminSite(AdminSite):
    site_header = "CropAI Administration"
    site_title = "CropAI Admin"
    index_title = "Dashboard Overview"

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        order = {label: i for i, label in enumerate(APP_PRIORITY)}
        app_list.sort(key=lambda app: order.get(app["app_label"], len(order)))
        for app in app_list:
            app["is_low_priority"] = app["app_label"] in LOW_PRIORITY_APPS
        return app_list

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

        district_count = Farm.objects.values("district").distinct().count()
        season_total = SeasonTracker.objects.count()

        # variant drives icon-color grouping in the template: "people" for
        # accounts, "land" for farm/season/harvest records, "activity" for
        # model/prediction usage — so color carries meaning instead of
        # just alternating decoratively.
        extra_context["dashboard_stats"] = [
            {
                "label": "Farmers",
                "value": User.objects.filter(role=User.Role.FARMER).count(),
                "icon": "fa-users",
                "trend": f"+{new_farmers_7} this week" if new_farmers_7 else "No new sign-ups",
                "trend_dir": "up" if new_farmers_7 else "flat",
                "variant": "people",
            },
            {
                "label": "Farms Registered",
                "value": Farm.objects.count(),
                "icon": "fa-tractor",
                "trend": f"Across {district_count} district{'s' if district_count != 1 else ''}",
                "trend_dir": "flat",
                "variant": "land",
            },
            {
                "label": "Predictions (7 days)",
                "value": pred_last_7,
                "icon": "fa-chart-line",
                "trend": f"{'+' if pred_delta >= 0 else ''}{pred_delta}% vs prior week",
                "trend_dir": "up" if pred_delta > 0 else ("down" if pred_delta < 0 else "flat"),
                "variant": "activity",
            },
            {
                "label": "Predictions (all time)",
                "value": Prediction.objects.count(),
                "icon": "fa-seedling",
                "trend": "Model inferences served",
                "trend_dir": "flat",
                "variant": "activity",
            },
            {
                "label": "Active Seasons",
                "value": SeasonTracker.objects.filter(status="Active").count(),
                "icon": "fa-calendar-check",
                "trend": f"{season_total} tracked in total",
                "trend_dir": "flat",
                "variant": "land",
            },
            {
                "label": "Harvest Reports",
                "value": HarvestFeedback.objects.count(),
                "icon": "fa-clipboard-check",
                "trend": "Feeding the soil model",
                "trend_dir": "flat",
                "variant": "land",
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

        recent_predictions = list(Prediction.objects.select_related("user").all()[:8])
        for pred in recent_predictions:
            pred.crop_icon, pred.crop_color = _crop_style(pred.predicted_crop)
        extra_context["recent_predictions"] = recent_predictions

        return super().index(request, extra_context)


admin.site.__class__ = CropAIAdminSite
