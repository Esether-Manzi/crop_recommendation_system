from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from farms.models import Farm

from .forms import PredictionForm
from .services.recommendation_services import RecommendationService


@login_required
def predict_crop(request):

    prediction = None
    recommendations = None
    selected_farm = None

    # Load all farms belonging to this user
    farms = Farm.objects.filter(user=request.user)

    # Check if farm is specified via query parameter or post data
    farm_id = request.GET.get("farm_id") or request.POST.get("farm_id")
    if farm_id:
        selected_farm = get_object_or_404(Farm, id=farm_id, user=request.user)

    if request.method == "POST":

        form = PredictionForm(request.POST)

        if form.is_valid():

            result = RecommendationService.create_prediction(
                request.user,
                form.cleaned_data,
                selected_farm,
            )

            prediction = result["prediction"]
            recommendations = result["recommendations"]

    else:
        # Prepopulate with the latest soil record values if farm is selected
        if selected_farm:
            latest_soil = selected_farm.soil_records.first()
            if latest_soil:
                form = PredictionForm(initial={
                    "nitrogen": latest_soil.nitrogen,
                    "phosphorus": latest_soil.phosphorus,
                    "potassium": latest_soil.potassium,
                    "ph": latest_soil.ph,
                    "temperature": latest_soil.temperature,
                    "humidity": latest_soil.humidity,
                    "rainfall": latest_soil.rainfall,
                })
            else:
                form = PredictionForm()
        else:
            form = PredictionForm()

    return render(
        request,
        "recommendations/predict.html",
        {
            "form": form,
            "prediction": prediction,
            "recommendations": recommendations,
            "farms": farms,
            "selected_farm": selected_farm,
        },
    )
