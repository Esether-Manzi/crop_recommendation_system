from django import forms

from ml.input_checks import HARD_LIMITS


def _number_field(name, placeholder=None):
    minimum, maximum = HARD_LIMITS[name]
    attrs = {"class": "form-control", "min": minimum, "max": maximum, "step": "any"}
    if placeholder:
        attrs["placeholder"] = placeholder
    return forms.FloatField(min_value=minimum, max_value=maximum, widget=forms.NumberInput(attrs=attrs))


class PredictionForm(forms.Form):

    nitrogen = _number_field("nitrogen")

    phosphorus = _number_field("phosphorus")

    potassium = _number_field("potassium")

    temperature = _number_field("temperature")

    humidity = _number_field("humidity")

    ph = _number_field("ph")

    rainfall = _number_field("rainfall", placeholder="e.g., 1200")
