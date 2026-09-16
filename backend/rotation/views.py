import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

from farms.models import Farm, SoilRecord
from .models import RotationPlan, RotationStep
from ml.datasets.sequential_pipeline import recommend_sequence

@login_required
def planner(request):
    farms = Farm.objects.filter(user=request.user)
    selected_farm = None
    plans = None
    latest_plan = None

    farm_id = request.GET.get("farm_id") or request.POST.get("farm_id")
    if farm_id:
        selected_farm = get_object_or_404(Farm, id=farm_id, user=request.user)
        # Fetch saved plans for this farm
        plans = RotationPlan.objects.filter(farm=selected_farm).prefetch_related("steps")
        latest_plan = plans.first()

    if request.method == "POST":
        if not selected_farm:
            messages.error(request, "Please select a farm to generate a rotation plan.")
            return redirect("rotation:planner")

        latest_soil = selected_farm.soil_records.first()
        if not latest_soil:
            messages.error(request, "No soil record found. Please add a soil log for this farm first!")
            return redirect("farms:detail", farm_id=selected_farm.id)

        # Run sequential recommendation
        base_ml_dir = os.path.join(settings.BASE_DIR, "ml")
        model_path = os.path.join(base_ml_dir, "model", "crop_model.pkl")
        encoder_path = os.path.join(base_ml_dir, "model", "crop_encoder.pkl")
        nutrient_table_path = os.path.join(base_ml_dir, "datasets", "Crop_Nutrient_Depletion_Table_All38.csv")

        initial_features = {
            "Nitrogen": latest_soil.nitrogen,
            "Phosphorus": latest_soil.phosphorus,
            "Potassium": latest_soil.potassium,
            "Temperature": latest_soil.temperature,
            "Humidity": latest_soil.humidity,
            "pH_Value": latest_soil.ph,
            "Rainfall": latest_soil.rainfall,
        }

        # Check if user configured fertilizer schedule
        fertilizer_applied = request.POST.get("fertilizer") == "yes"
        fertilizer_schedule = [fertilizer_applied] * 4 # Apply same for all 4 seasons

        try:
            history = recommend_sequence(
                model_path=model_path,
                encoder_path=encoder_path,
                nutrient_table_path=nutrient_table_path,
                initial_features=initial_features,
                n_seasons=4,
                avoid_repeat_family=True,
                fertilizer_schedule=fertilizer_schedule
            )

            # Save the plan to the database
            plan = RotationPlan.objects.create(farm=selected_farm)
            for h in history:
                RotationStep.objects.create(
                    plan=plan,
                    season_number=h["season"],
                    crop_recommended=h["crop_recommended"],
                    crop_family=h["crop_family"],
                    fertilizer_applied=h["fertilizer_applied"],
                    nitrogen_before=h["features_before"]["Nitrogen"],
                    phosphorus_before=h["features_before"]["Phosphorus"],
                    potassium_before=h["features_before"]["Potassium"],
                    ph_before=h["features_before"]["pH_Value"],
                    nitrogen_after=h["features_after"]["Nitrogen"],
                    phosphorus_after=h["features_after"]["Phosphorus"],
                    potassium_after=h["features_after"]["Potassium"],
                    ph_after=h["features_after"]["pH_Value"]
                )

            messages.success(request, "Your 4-season rotation plan is ready!")
            return redirect(f"{request.path}?farm_id={selected_farm.id}")

        except Exception:
            messages.error(request, "Unable to generate a rotation plan right now. Please try again later.")
            return redirect(f"{request.path}?farm_id={selected_farm.id}")

    return render(request, "rotation/planner.html", {
        "farms": farms,
        "selected_farm": selected_farm,
        "plans": plans,
        "latest_plan": latest_plan,
    })
