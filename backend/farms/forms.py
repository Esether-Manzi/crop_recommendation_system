from datetime import date

from django import forms

from ml.input_checks import HARD_LIMITS
from .models import Farm, SoilRecord

class FarmForm(forms.ModelForm):
    class Meta:
        model = Farm
        fields = ["farm_name", "district", "subcounty", "size_acres", "soil_type", "latitude", "longitude"]
        widgets = {
            "farm_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., North Field"}),
            "district": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Mbarara"}),
            "subcounty": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Kakoba"}),
            "size_acres": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 2.5", "step": "0.1"}),
            "soil_type": forms.Select(attrs={"class": "form-select"}),
            "latitude": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., -0.61 (optional)", "step": "any"}),
            "longitude": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 30.65 (optional)", "step": "any"}),
        }


class SoilRecordForm(forms.ModelForm):
    class Meta:
        model = SoilRecord
        fields = ["nitrogen", "phosphorus", "potassium", "ph", "temperature", "humidity", "rainfall", "source", "tested_on"]
        widgets = {
            "nitrogen": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 50.0", "step": "any"}),
            "phosphorus": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 25.0", "step": "any"}),
            "potassium": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 35.0", "step": "any"}),
            "ph": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 6.5", "step": "any"}),
            "temperature": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 22.0", "step": "any"}),
            "humidity": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 75.0", "step": "any"}),
            "rainfall": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 1000", "step": "any"}),
            "source": forms.Select(attrs={"class": "form-select"}),
            "tested_on": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # "Calculated after a harvest" records are only created by the feedback flow.
        self.fields["source"].choices = [
            choice for choice in self.fields["source"].choices
            if choice[0] != SoilRecord.Source.SIMULATED
        ]

    def clean_tested_on(self):
        tested_on = self.cleaned_data.get("tested_on")
        if tested_on and tested_on > date.today():
            raise forms.ValidationError("The test date can't be in the future.")
        return tested_on

    def clean(self):
        cleaned_data = super().clean()
        for field, (minimum, maximum) in HARD_LIMITS.items():
            value = cleaned_data.get(field)
            if value is not None and not minimum <= value <= maximum:
                self.add_error(field, f"Enter a value between {minimum} and {maximum}.")
        return cleaned_data
