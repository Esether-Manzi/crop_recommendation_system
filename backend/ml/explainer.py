"""
XAI Explainer Module
=====================
Uses SHAP TreeExplainer to produce per-feature contribution scores for each
individual crop prediction made by the XGBoost model.

Why TreeExplainer?
- XGBoost is a gradient-boosted tree ensemble — TreeExplainer computes
  exact Shapley values in O(TLD) time (T=trees, L=leaves, D=depth).
- Much faster than KernelExplainer, and mathematically exact.

Output per feature:
    {
        "feature":          "Nitrogen",
        "display_name":     "Nitrogen (N)",
        "unit":             "mg/kg",
        "value":            80.0,       # what the user entered
        "contribution":     0.42,       # raw SHAP value (positive = pushes toward this crop)
        "direction":        "positive", # "positive" | "negative"
        "abs_contribution": 0.42,
        "pct_of_total":     34.1,       # % share of the total |SHAP| mass for this prediction
    }
"""

import shap
import pandas as pd
import numpy as np

from .loader import model, encoder, feature_names

# ── Human-readable display metadata ────────────────────────────────────────────
FEATURE_META = {
    "Nitrogen":    {"display": "Nitrogen (N)",    "unit": "mg/kg"},
    "Phosphorus":  {"display": "Phosphorus (P)",  "unit": "mg/kg"},
    "Potassium":   {"display": "Potassium (K)",   "unit": "mg/kg"},
    "Temperature": {"display": "Temperature",     "unit": "°C"},
    "Humidity":    {"display": "Humidity",        "unit": "%"},
    "pH_Value":    {"display": "Soil pH",         "unit": ""},
    "Rainfall":    {"display": "Rainfall",        "unit": "mm"},
}

# ── Fertilizer boost constants (mirrored from sequential_pipeline.py) ───────────
# Applied per-season: N +40 kg/ha, P +20 kg/ha, K +15 kg/ha (converted by /2.6)
FERTILIZER_BOOST = {
    "Nitrogen":   round(40 / 2.6, 2),   # ≈ +15.38 mg/kg
    "Phosphorus": round(20 / 2.6, 2),   # ≈ +7.69 mg/kg
    "Potassium":  round(15 / 2.6, 2),   # ≈ +5.77 mg/kg
}

# ── Cached explainer (expensive to build, reused across requests) ────────────
_explainer = None


def _get_explainer():
    global _explainer
    if _explainer is None:
        _explainer = shap.TreeExplainer(model)
    return _explainer


def explain_prediction(data: dict, crop_name: str) -> list[dict]:
    """
    Compute SHAP feature contributions for a specific crop prediction.

    Parameters
    ----------
    data : dict
        Feature dict with keys matching `feature_names`
        e.g. {"Nitrogen": 80, "Phosphorus": 40, ...}
    crop_name : str
        The crop whose SHAP values we want
        (must match a class in the encoder)

    Returns
    -------
    list[dict]
        Sorted by absolute contribution (most influential first).
        Empty list if crop not found in encoder.
    """
    explainer = _get_explainer()

    input_df = pd.DataFrame([data])[feature_names]

    # shap_values shape for multi-class: (n_samples, n_features, n_classes)
    # or list of arrays — handle both formats XGBoost may return
    raw_shap = explainer.shap_values(input_df)

    crop_classes = list(encoder.classes_)
    try:
        crop_idx = crop_classes.index(crop_name)
    except ValueError:
        return []

    # Normalise to (n_features,) for this single sample and this crop class
    if isinstance(raw_shap, np.ndarray) and raw_shap.ndim == 3:
        # shape (n_samples, n_features, n_classes)
        feature_shap = raw_shap[0, :, crop_idx]
    elif isinstance(raw_shap, list):
        # list of arrays, one per class, each (n_samples, n_features)
        feature_shap = raw_shap[crop_idx][0]
    else:
        # 2-D fallback (binary or single output)
        feature_shap = raw_shap[0]

    # Total absolute mass — used to compute percentage shares
    total_abs = float(np.sum(np.abs(feature_shap))) or 1.0

    results = []
    for i, fname in enumerate(feature_names):
        contribution = float(feature_shap[i])
        abs_c = abs(contribution)
        meta = FEATURE_META.get(fname, {"display": fname, "unit": ""})
        results.append({
            "feature":          fname,
            "display_name":     meta["display"],
            "unit":             meta["unit"],
            "value":            data[fname],
            "contribution":     round(contribution, 4),
            "direction":        "positive" if contribution >= 0 else "negative",
            "abs_contribution": round(abs_c, 4),
            "pct_of_total":     round((abs_c / total_abs) * 100, 1),
        })

    # Most influential first
    results.sort(key=lambda x: x["abs_contribution"], reverse=True)
    return results


def get_fertilizer_boosted_inputs(data: dict) -> dict:
    """
    Return a copy of `data` with fertilizer nutrients added.
    Only Nitrogen, Phosphorus, Potassium are boosted — climate features
    (Temperature, Humidity, Rainfall, pH) are not affected by fertilizer.
    """
    boosted = dict(data)
    for nutrient, delta in FERTILIZER_BOOST.items():
        if nutrient in boosted:
            boosted[nutrient] = round(boosted[nutrient] + delta, 2)
    return boosted
