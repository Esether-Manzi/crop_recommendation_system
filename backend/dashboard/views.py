from django.shortcuts import render
from farms.models import Farm
from advisory.models import SeasonTracker
from recommendations.models import Prediction
from feedback.models import HarvestFeedback


def dashboard_home(request):
    if not request.user.is_authenticated:
        return render(request, "home/index.html")

    farms = Farm.objects.filter(user=request.user)
    active_trackers = SeasonTracker.objects.filter(farm__user=request.user, status="Active")
    recent_predictions = Prediction.objects.filter(user=request.user)[:5]
    recent_feedbacks = HarvestFeedback.objects.filter(farm__user=request.user)[:5]

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
        },
    )
