import os
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

from farms.models import Farm, SoilRecord
from .models import HarvestFeedback

# topsoil conversion factor (1 mg/kg ppm ~ 2.6 kg/ha)
CONVERSION_FACTOR = 2.6

@login_required
def feedback_submit(request):
    farms = Farm.objects.filter(user=request.user)

    if request.method == "POST":
        farm_id = request.POST.get("farm_id")
        crop_name = request.POST.get("crop_name", "").strip()
        yield_rating = request.POST.get("yield_rating")
        satisfaction = request.POST.get("satisfaction_score")
        residue = request.POST.get("residue_management")
        comments = request.POST.get("comments", "")

        if not farm_id or not crop_name or not yield_rating or not satisfaction or not residue:
            messages.error(request, "Please fill in all required fields.")
            return redirect("feedback:submit")

        farm = get_object_or_404(Farm, id=farm_id, user=request.user)

        # Save harvest feedback record
        feedback = HarvestFeedback.objects.create(
            farm=farm,
            crop_name=crop_name,
            yield_rating=yield_rating,
            satisfaction_score=int(satisfaction),
            residue_management=residue,
            comments=comments
        )

        # Retrieve the latest soil record to adapt
        latest_soil = farm.soil_records.first()
        if latest_soil:
            nutrient_table_path = os.path.join(settings.BASE_DIR, "ml", "datasets", "Crop_Nutrient_Depletion_Table_All38.csv")
            try:
                nutrient_table = pd.read_csv(nutrient_table_path).set_index("Crop")
                
                # Check for matching crop
                matched_crop = None
                for c in nutrient_table.index:
                    if c.lower() == crop_name.lower():
                        matched_crop = c
                        break

                if matched_crop:
                    row = nutrient_table.loc[matched_crop]
                    
                    # Yield scale factor
                    yield_scales = {
                        "Good": 1.0,
                        "Average": 0.75,
                        "Poor": 0.45,
                        "Failed": 0.15
                    }
                    scale = yield_scales.get(yield_rating, 1.0)
                    
                    n_fix = row["N_Fixation_kg_ha"]
                    n_uptake = row["N_Uptake_kg_ha"] * scale
                    p_uptake = row["P_Uptake_kg_ha"] * scale
                    k_uptake = row["K_Uptake_kg_ha"] * scale

                    n_delta = (n_fix - n_uptake) / CONVERSION_FACTOR
                    
                    # Residue management: if residues are incorporated, return 30% of extracted nutrients
                    if residue == "Incorporated":
                        p_delta = -(p_uptake * 0.70) / CONVERSION_FACTOR
                        k_delta = -(k_uptake * 0.70) / CONVERSION_FACTOR
                    else:
                        p_delta = -p_uptake / CONVERSION_FACTOR
                        k_delta = -k_uptake / CONVERSION_FACTOR

                    new_n = max(0, round(latest_soil.nitrogen + n_delta, 2))
                    new_p = max(0, round(latest_soil.phosphorus + p_delta, 2))
                    new_k = max(0, round(latest_soil.potassium + k_delta, 2))
                    
                    # pH decay
                    ph_delta = -0.03 if row["Demand_Class"] in ["Heavy feeder", "Very heavy feeder"] else 0.01
                    new_ph = round(min(max(latest_soil.ph + ph_delta, 3.5), 8.5), 2)

                    # Create newly updated soil record representing soil state after crop harvest
                    SoilRecord.objects.create(
                        farm=farm,
                        nitrogen=new_n,
                        phosphorus=new_p,
                        potassium=new_k,
                        ph=new_ph,
                        temperature=latest_soil.temperature,
                        humidity=latest_soil.humidity,
                        rainfall=latest_soil.rainfall
                    )
                    messages.success(request, "Harvest feedback saved! We've updated your farm's soil record.")
                else:
                    messages.warning(request, f"Feedback saved, but we don't have soil data for '{crop_name}' yet, so we couldn't update your soil record.")
            except Exception:
                messages.warning(request, "Feedback saved, but we couldn't update your soil record this time.")
        else:
            messages.warning(request, "Feedback saved, but there's no soil record yet to update.")

        # Archive active trackers for this crop
        from advisory.models import SeasonTracker
        active_trackers = SeasonTracker.objects.filter(farm=farm, crop_name__iexact=crop_name, status="Active")
        if active_trackers.exists():
            active_trackers.update(status="Completed")

        return redirect("farms:detail", farm_id=farm.id)

    return render(request, "feedback/submit.html", {
        "farms": farms,
    })
