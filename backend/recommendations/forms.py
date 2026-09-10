from django import forms

class PredictionForm(forms.Form):

    nitrogen = forms.FloatField(
        min_value=0, max_value=1000,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 1000})
    )

    phosphorus = forms.FloatField(
        min_value=0, max_value=1000,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 1000})
    )

    potassium = forms.FloatField(
        min_value=0, max_value=1000,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 1000})
    )

    temperature = forms.FloatField(
        min_value=-10, max_value=60,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": -10, "max": 60, "step": "any"})
    )

    humidity = forms.FloatField(
        min_value=0, max_value=100,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 100, "step": "any"})
    )

    ph = forms.FloatField(
        min_value=3.5, max_value=8.5,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 3.5, "max": 8.5, "step": "any"})
    )

    rainfall = forms.FloatField(
        min_value=0, max_value=10000,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 10000})
    )
