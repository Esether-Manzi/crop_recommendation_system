from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .forms import PredictionForm
from .services.recommendation_services import RecommendationService


@login_required
def predict_crop(request):

    prediction = None
    suitability = None

    if request.method == "POST":

        form = PredictionForm(request.POST)

        if form.is_valid():

            result = RecommendationService.create_prediction(
                request.user,
                form.cleaned_data,
            )

            prediction = result["prediction"]
            suitability = result["suitability"]

    else:
        form = PredictionForm()

    return render(
        request,
        "recommendations/predict.html",
        {
            "form": form,
            "prediction": prediction,
            "suitability": suitability,
        },
    )