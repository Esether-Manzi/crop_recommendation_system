"""
Checks on soil and weather values entered by farmers (panel comment 7).

Three layers, from strictest to softest:

1. HARD_LIMITS  — physically or agronomically impossible values. The forms
                  reject these, so they never reach the model.
2. check_inputs — values that are possible but deserve a warning. The
                  prediction still runs, the warnings are shown next to it
                  and saved on the Prediction:
                  - likely unit mistakes (e.g. N reported as %, monthly rainfall)
                  - values outside the range the model was trained on
                  - soil whose combination of values doesn't resemble any
                    crop in the training data (the model's confidence is
                    unreliable there). With the Naive Bayes model this uses
                    the model's own likelihood: the soil is flagged when it is
                    less likely, under its best-matching crop, than 99% of the
                    real training soils. For other model types it falls back
                    to counting how many values fall inside some crop's range.
3. check_soil_test — where the numbers came from: lab test, home kit,
                  estimate, or calculated by the app after a harvest, and how
                  old the underlying test is.

All values are in the units farmers enter (rainfall in mm per YEAR). Ranges
come from the files `manage.py train_model` writes, so they always match the
deployed model.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.naive_bayes import GaussianNB

from .features import FEATURE_NAMES, RAINFALL_MONTHS, build_model_input
from .loader import model

ML_DIR = Path(__file__).resolve().parent
TRAINING_DATA_PATH = ML_DIR / "model" / "training_dataset_harmonised.csv"
SUITABILITY_PATH = ML_DIR / "datasets" / "Uganda_Crop_Suitability_Ranges.csv"

# form field -> (training-data column, suitability min column, suitability max column, label, unit)
FIELDS = {
    "nitrogen": ("Nitrogen", "N_min", "N_max", "Nitrogen (N)", "mg/kg"),
    "phosphorus": ("Phosphorus", "P_min", "P_max", "Phosphorus (P)", "mg/kg"),
    "potassium": ("Potassium", "K_min", "K_max", "Potassium (K)", "mg/kg"),
    "temperature": ("Temperature", "Temp_min", "Temp_max", "Temperature", "°C"),
    "humidity": ("Humidity", "Hum_min", "Hum_max", "Humidity", "%"),
    "ph": ("pH_Value", "pH_min", "pH_max", "Soil pH", ""),
    "rainfall": ("Rainfall", "Rain_min", "Rain_max", "Rainfall", "mm/year"),
}

# Layer 1: values outside these are rejected by the forms.
HARD_LIMITS = {
    "nitrogen": (0, 1000),
    "phosphorus": (0, 1000),
    "potassium": (0, 1000),
    "temperature": (0, 45),      # average temperature; Uganda's range is roughly 15-30 °C
    "humidity": (0, 100),
    "ph": (3.5, 8.5),
    "rainfall": (0, 5000),       # annual; Uganda's wettest areas get about 2,500 mm
}

# Naive Bayes check: flag soil less likely than this share of training soils.
UNUSUAL_SOIL_PERCENTILE = 1

# Fallback check for other models: a soil is "like" a crop when at least this
# many of its 7 values fall inside that crop's training range.
MIN_FEATURES_MATCHING_A_CROP = 5

# Annual rainfall below this is more likely a monthly figure than real
# Ugandan rainfall (the driest areas get about 500 mm a year).
LIKELY_MONTHLY_RAINFALL_MM = 300

SOIL_TEST_MAX_AGE_YEARS = 3


@lru_cache(maxsize=1)
def _training_data():
    return pd.read_csv(TRAINING_DATA_PATH)


@lru_cache(maxsize=1)
def training_ranges():
    """Min/max of each field across the model's training data, in farmer units."""
    data = _training_data()
    ranges = {}
    for field, (column, *_rest) in FIELDS.items():
        low, high = float(data[column].min()), float(data[column].max())
        if field == "rainfall":
            low, high = low * RAINFALL_MONTHS, high * RAINFALL_MONTHS
        ranges[field] = (low, high)
    return ranges


def _best_crop_log_likelihood(X):
    """log p(x | crop) for the best-matching crop, per row (Gaussian NB only)."""
    X = np.atleast_2d(X)
    log_likelihood = -0.5 * (
        np.log(2 * np.pi * model.var_)[None] + (X[:, None, :] - model.theta_[None]) ** 2 / model.var_[None]
    )
    return log_likelihood.sum(axis=2).max(axis=1)


@lru_cache(maxsize=1)
def unusual_soil_threshold():
    return float(np.percentile(
        _best_crop_log_likelihood(_training_data()[FEATURE_NAMES].to_numpy(dtype=float)),
        UNUSUAL_SOIL_PERCENTILE,
    ))


def is_unusual_soil(values):
    if isinstance(model, GaussianNB):
        features = build_model_input(**{("annual_rainfall" if k == "rainfall" else k): v for k, v in values.items()})
        score = _best_crop_log_likelihood([[features[f] for f in FEATURE_NAMES]])[0]
        return score < unusual_soil_threshold()
    best, _crops = best_matching_crops(values)
    return best < MIN_FEATURES_MATCHING_A_CROP


@lru_cache(maxsize=1)
def crop_ranges():
    return pd.read_csv(SUITABILITY_PATH)


def _fmt(value, unit):
    return f"{value:g} {unit}".strip()


def best_matching_crops(values):
    """(number of values inside the best crop's range, crops achieving it)."""
    crops = crop_ranges()
    in_range = sum(
        ((crops[min_col] <= values[field]) & (values[field] <= crops[max_col])).astype(int)
        for field, (_col, min_col, max_col, _label, _unit) in FIELDS.items()
    )
    best = int(in_range.max())
    return best, crops.loc[in_range == best, "Crop"].tolist()


def check_inputs(values):
    """values: {"nitrogen": .., ..., "rainfall": annual mm}. Returns a list of
    {"code", "level": "warning" | "info", "field", "message"} dicts."""
    warnings = []

    for field in ("nitrogen", "phosphorus", "potassium"):
        if 0 < values[field] < 1:
            label = FIELDS[field][3]
            warnings.append({
                "code": "unit",
                "level": "warning",
                "field": field,
                "message": (
                    f"{label} is {values[field]:g}. Values below 1 usually mean the lab report uses a "
                    f"different unit (for example % or cmol/kg). This field needs mg/kg; see "
                    f"'How do I fill this in?' above the form."
                ),
            })

    if 0 < values["rainfall"] < LIKELY_MONTHLY_RAINFALL_MM:
        warnings.append({
            "code": "unit",
            "level": "warning",
            "field": "rainfall",
            "message": (
                f"Rainfall is {values['rainfall']:g} mm per year, which is very dry for Uganda "
                f"(the driest areas get about 500 mm). If this is a monthly figure, multiply it by 12."
            ),
        })

    for field, (low, high) in training_ranges().items():
        value = values[field]
        if not low <= value <= high:
            _col, _min, _max, label, unit = FIELDS[field]
            warnings.append({
                "code": "outside_training_range",
                "level": "warning",
                "field": field,
                "message": (
                    f"{label} ({_fmt(value, unit)}) is outside the values our model learned from "
                    f"({_fmt(low, unit)} to {_fmt(high, unit)}), so treat the result with care."
                ),
            })

    if is_unusual_soil(values):
        warnings.append({
            "code": "unusual_soil",
            "level": "warning",
            "field": None,
            "message": (
                "This combination of values is very different from the soils our model learned from, "
                "so the recommendation and its confidence score are less reliable. "
                "Please double-check your soil test."
            ),
        })

    return warnings


def check_soil_test(source, tested_on, today=None):
    """Warnings about where soil values came from. source is a SoilRecord.Source value."""
    today = today or date.today()
    warnings = []
    if source == "estimate":
        warnings.append({
            "code": "estimated",
            "level": "warning",
            "field": None,
            "message": "These soil values are an estimate, not a test. A lab soil test will give a much more reliable recommendation.",
        })
    elif source == "simulated":
        warnings.append({
            "code": "simulated",
            "level": "info",
            "field": None,
            "message": (
                "These soil values were calculated by the app from your harvest report, not measured. "
                "A new soil test will give a more reliable recommendation."
            ),
        })
    elif source == "kit":
        warnings.append({
            "code": "home_kit",
            "level": "info",
            "field": None,
            "message": "These soil values come from a home test kit, which is less precise than a lab test.",
        })
    if tested_on and (today - tested_on).days > SOIL_TEST_MAX_AGE_YEARS * 365:
        years = (today - tested_on).days // 365
        warnings.append({
            "code": "old_test",
            "level": "warning",
            "field": None,
            "message": f"This soil test is {years} years old. Soil changes over time; consider testing again.",
        })
    return warnings
