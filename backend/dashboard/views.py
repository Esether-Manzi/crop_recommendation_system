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
                    "message": f"Nitrogen is very low ({latest_soil.nitrogen} mg/kg) on '{farm.farm_name}'. Planting legumes like beans or groundnuts next can help build it back up."
                })
            if latest_soil.phosphorus < 20:
                alerts.append({
                    "farm": farm,
                    "type": "danger",
                    "message": f"Phosphorus is very low ({latest_soil.phosphorus} mg/kg) on '{farm.farm_name}'. A phosphorus-rich fertilizer like DAP before your next planting can help roots grow stronger."
                })
            if latest_soil.potassium < 30:
                alerts.append({
                    "farm": farm,
                    "type": "danger",
                    "message": f"Potassium is very low ({latest_soil.potassium} mg/kg) on '{farm.farm_name}'. A potassium-rich fertilizer like Muriate of Potash, or leaving crop residues in the field, can help build it back up."
                })
            if latest_soil.ph < 5.0 or latest_soil.ph > 8.0:
                alerts.append({
                    "farm": farm,
                    "type": "warning",
                    "message": f"Soil pH on '{farm.farm_name}' is out of the ideal range ({latest_soil.ph}), which can make it harder for most crops to grow well. Adding lime can help balance it."
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
