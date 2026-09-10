from collections import Counter
from datetime import timedelta

from django.shortcuts import render
from django.utils import timezone
from farms.models import Farm, SoilRecord
from advisory.models import SeasonTracker
from advisory.services import compute_season_progress
from recommendations.models import Prediction
from feedback.models import HarvestFeedback


def image_credits(request):
    return render(request, "dashboard/image_credits.html")


def dashboard_home(request):
    if not request.user.is_authenticated:
        return render(request, "home/index.html")

    farms = Farm.objects.filter(user=request.user)
    active_trackers = [
        {"tracker": tracker, **compute_season_progress(tracker)}
        for tracker in SeasonTracker.objects.filter(farm__user=request.user, status="Active")
    ]
    all_predictions = Prediction.objects.filter(user=request.user)
    recent_predictions = all_predictions[:5]
    recent_feedbacks = HarvestFeedback.objects.filter(farm__user=request.user)[:5]

    # Prediction activity for the last 6 calendar months (chart data)
    now = timezone.now()
    month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    months = []
    cursor = month_start
    for _ in range(6):
        months.append(cursor)
        # step back one month
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    months.reverse()

    month_labels, month_counts = [], []
    for start in months:
        next_month = (start + timedelta(days=32)).replace(day=1)
        month_labels.append(start.strftime("%b"))
        month_counts.append(
            all_predictions.filter(
                created_at__gte=start, created_at__lt=next_month
            ).count()
        )

    # Most-recommended crop across this farmer's history
    crop_counter = Counter(all_predictions.values_list("predicted_crop", flat=True))
    top_crop, top_crop_count = (crop_counter.most_common(1)[0] if crop_counter else (None, 0))

    # Latest soil snapshot from the most recently updated farm
    latest_soil = (
        SoilRecord.objects.filter(farm__user=request.user)
        .select_related("farm")
        .first()
    )

    # Calculate soil alerts
    alerts = []
    for farm in farms:
        latest_soil = farm.soil_records.first()
        if latest_soil:
            if latest_soil.nitrogen < 30:
                alerts.append({
                    "farm": farm,
                    "type": "danger",
                    "message": f"Critical low Nitrogen ({latest_soil.nitrogen} mg/kg) detected on '{farm.farm_name}'. Consider planting legumes (e.g. Beans/Groundnuts) next to restore soil organic matter."
                })
            if latest_soil.ph < 5.0 or latest_soil.ph > 8.0:
                alerts.append({
                    "farm": farm,
                    "type": "warning",
                    "message": f"Suboptimal soil pH ({latest_soil.ph}) on '{farm.farm_name}'. Suitability rates might decay. Standard lime application may be required."
                })

    return render(
        request,
        "dashboard/home.html",
        {
            "farms_count": farms.count(),
            "farms": farms[:3],
            "active_trackers": active_trackers,
            "recent_predictions": recent_predictions,
            "recent_feedbacks": recent_feedbacks,
            "alerts": alerts,
            "predictions_total": all_predictions.count(),
            "feedbacks_total": HarvestFeedback.objects.filter(farm__user=request.user).count(),
            "chart_labels": month_labels,
            "chart_counts": month_counts,
            "top_crop": top_crop,
            "top_crop_count": top_crop_count,
            "latest_soil": latest_soil,
        },
    )
