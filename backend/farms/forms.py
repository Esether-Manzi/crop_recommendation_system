from django import forms
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
        fields = ["nitrogen", "phosphorus", "potassium", "ph", "temperature", "humidity", "rainfall"]
        widgets = {
            "nitrogen": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 50.0"}),
            "phosphorus": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 25.0"}),
            "potassium": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 35.0"}),
            "ph": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 6.5", "step": "any"}),
            "temperature": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 22.0", "step": "any"}),
            "humidity": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 75.0", "step": "any"}),
            "rainfall": forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g., 1000.0", "step": "1.0"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        limits = {
            "nitrogen": (0, 1000), "phosphorus": (0, 1000), "potassium": (0, 1000),
            "ph": (3.5, 8.5), "temperature": (-10, 60), "humidity": (0, 100),
            "rainfall": (0, 10000),
        }
        for field, (minimum, maximum) in limits.items():
            value = cleaned_data.get(field)
            if value is not None and not minimum <= value <= maximum:
                self.add_error(field, f"Enter a value between {minimum} and {maximum}.")
        return cleaned_data
