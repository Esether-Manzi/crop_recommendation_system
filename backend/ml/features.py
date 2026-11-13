"""
Single place where user-entered values become model features.

The model is trained on a monthly rainfall scale: the Kaggle rows use it
natively, and the synthetic Uganda rows (generated from annual FAO EcoCrop
ranges) are divided by RAINFALL_MONTHS in ml/training.py. Farmers enter
annual rainfall, so every caller that feeds the model must go through
build_model_input() rather than building the feature dict by hand.
"""

FEATURE_NAMES = ["Nitrogen", "Phosphorus", "Potassium", "Temperature", "Humidity", "pH_Value", "Rainfall"]

RAINFALL_MONTHS = 12


def annual_to_model_rainfall(annual_mm):
    return round(annual_mm / RAINFALL_MONTHS, 2)


def model_to_annual_rainfall(model_mm):
    return round(model_mm * RAINFALL_MONTHS, 1)


def build_model_input(nitrogen, phosphorus, potassium, temperature, humidity, ph, annual_rainfall):
    return {
        "Nitrogen": nitrogen,
        "Phosphorus": phosphorus,
        "Potassium": potassium,
        "Temperature": temperature,
        "Humidity": humidity,
        "pH_Value": ph,
        "Rainfall": annual_to_model_rainfall(annual_rainfall),
    }
