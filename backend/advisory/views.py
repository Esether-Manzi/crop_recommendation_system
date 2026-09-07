from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from farms.models import Farm
from .models import CropAdvisory, SeasonTracker

@login_required
def advisory_list(request):
    # Fetch all crops with guidelines
    available_crops = CropAdvisory.objects.values_list("crop_name", flat=True).distinct()
    selected_crop = request.GET.get("crop", "").strip().lower()

    advisories = []
    if selected_crop:
        advisories = CropAdvisory.objects.filter(crop_name=selected_crop)

    return render(request, "advisory/advisory_list.html", {
        "crops": available_crops,
        "selected_crop": selected_crop,
        "advisories": advisories,
    })

@login_required
def season_tracker(request):
    farms = Farm.objects.filter(user=request.user)
    trackers = SeasonTracker.objects.filter(farm__user=request.user)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "start":
            farm_id = request.POST.get("farm_id")
            crop_name = request.POST.get("crop_name", "").strip().lower()
            start_date_str = request.POST.get("start_date")

            if not farm_id or not crop_name or not start_date_str:
                messages.error(request, "Please fill in all details to start tracking.")
                return redirect("advisory:tracker")

            farm = get_object_or_404(Farm, id=farm_id, user=request.user)

            # Create the tracker
            SeasonTracker.objects.create(
                farm=farm,
                crop_name=crop_name,
                start_date=start_date_str,
                status="Active"
            )
            messages.success(request, f"Started tracking {crop_name.title()} on farm '{farm.farm_name}'!")
            return redirect("advisory:tracker")

        elif action == "complete":
            tracker_id = request.POST.get("tracker_id")
            tracker = get_object_or_404(SeasonTracker, id=tracker_id, farm__user=request.user)
            tracker.status = "Completed"
            tracker.save()
            messages.success(request, f"Marked season for {tracker.crop_name.title()} as completed. Please log harvest feedback next.")
            return redirect("feedback:submit")

    active_trackers_data = []
    for tracker in trackers.filter(status="Active"):
        today = date.today()
        elapsed_days = (today - tracker.start_date).days
        elapsed_weeks = max(1, (elapsed_days // 7) + 1)

        # Map growth week to actionable advisory stages
        if elapsed_weeks <= 2:
            stages = ["Preparation", "Planting"]
        elif elapsed_weeks <= 5:
            stages = ["Weeding", "Fertilizer"]
        elif elapsed_weeks <= 9:
            stages = ["Pests", "Diseases"]
        else:
            stages = ["Harvest", "Storage"]

        # Fetch current stage advisories
        advisories = CropAdvisory.objects.filter(crop_name=tracker.crop_name.lower(), stage__in=stages)

        # Assume 14 weeks is full crop maturity
        progress = min(100, int((elapsed_weeks / 14) * 100))

        active_trackers_data.append({
            "tracker": tracker,
            "weeks": elapsed_weeks,
            "days": elapsed_days,
            "stages": stages,
            "advisories": advisories,
            "progress": progress,
        })

    completed_trackers = trackers.filter(status="Completed")
    available_crops = CropAdvisory.objects.values_list("crop_name", flat=True).distinct()

    return render(request, "advisory/tracker.html", {
        "farms": farms,
        "active_trackers": active_trackers_data,
        "completed_trackers": completed_trackers,
        "available_crops": available_crops,
    })
