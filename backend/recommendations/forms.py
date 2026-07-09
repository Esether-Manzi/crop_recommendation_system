from django import forms



class PredictionForm(forms.Form):

    nitrogen = forms.FloatField(
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    phosphorus = forms.FloatField(
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    potassium = forms.FloatField(
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    temperature = forms.FloatField(
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    humidity = forms.FloatField(
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    ph = forms.FloatField(
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    rainfall = forms.FloatField(
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )