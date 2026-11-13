from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ml.input_checks import check_inputs, check_soil_test
from .models import Farm, SoilRecord
from .forms import FarmForm, SoilRecordForm

@login_required
def farms_list(request):
    farms = Farm.objects.filter(user=request.user)
    if request.method == "POST":
        form = FarmForm(request.POST)
        if form.is_valid():
            farm = form.save(commit=False)
            farm.user = request.user
            farm.save()
            messages.success(request, f"Farm '{farm.farm_name}' added successfully!")
            return redirect("farms:list")
    else:
        form = FarmForm()
    return render(request, "farms/farms_list.html", {"farms": farms, "form": form})

@login_required
def farm_detail(request, farm_id):
    farm = get_object_or_404(Farm, id=farm_id, user=request.user)
    soil_records = farm.soil_records.all()
    
    if request.method == "POST":
        form = SoilRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.farm = farm
            record.save()
            messages.success(request, "New soil record added successfully!")
            values = {f: getattr(record, f) for f in ("nitrogen", "phosphorus", "potassium", "temperature", "humidity", "ph", "rainfall")}
            for warning in check_inputs(values) + check_soil_test(record.source, record.tested_on):
                (messages.info if warning["level"] == "info" else messages.warning)(request, warning["message"])
            return redirect("farms:detail", farm_id=farm.id)
    else:
        # Prepopulate with the latest soil record values if available
        latest = soil_records.first()
        if latest:
            form = SoilRecordForm(initial={
                "nitrogen": latest.nitrogen,
                "phosphorus": latest.phosphorus,
                "potassium": latest.potassium,
                "ph": latest.ph,
                "temperature": latest.temperature,
                "humidity": latest.humidity,
                "rainfall": latest.rainfall,
                "source": latest.source if latest.source != SoilRecord.Source.SIMULATED else SoilRecord.Source.LAB,
                "tested_on": latest.tested_on,
            })
        else:
            form = SoilRecordForm()

    return render(request, "farms/farm_detail.html", {
        "farm": farm,
        "soil_records": soil_records,
        "form": form,
    })
