"""
XAI Explainer Module
=====================
Produces per-feature contribution scores for each individual crop prediction.
The method depends on which model `manage.py train_model` deployed:

Gaussian Naive Bayes (exact, closed form)
- NB scores a crop as log P(crop) + sum over features of log p(value | crop),
  so each feature's influence is directly separable. A feature's contribution
  is its log-likelihood ratio against the average crop:
      log p(x_i | crop) - log sum_k P(k) p(x_i | k)
  Positive = this value is more typical of this crop than of crops in general.

Tree ensembles (XGBoost, Random Forest, ...) via SHAP TreeExplainer
- Computes exact Shapley values in O(TLD) time (T=trees, L=leaves, D=depth).

Any other model type returns an empty list, which the UI already handles.

Output per feature:
    {
        "feature":          "Nitrogen",
        "display_name":     "Nitrogen (N)",
        "unit":             "mg/kg",
        "value":            80.0,       # what the user entered
        "contribution":     0.42,       # positive = pushes toward this crop
        "direction":        "positive", # "positive" | "negative"
        "abs_contribution": 0.42,
        "pct_of_total":     34.1,       # % share of the total |contribution| mass for this prediction
    }
"""

import shap
import pandas as pd
import numpy as np
from scipy.special import logsumexp
from sklearn.naive_bayes import GaussianNB

from .loader import model, encoder, feature_names

# ── Human-readable display metadata ────────────────────────────────────────────
FEATURE_META = {
    "Nitrogen":    {"display": "Nitrogen (N)",    "unit": "mg/kg"},
    "Phosphorus":  {"display": "Phosphorus (P)",  "unit": "mg/kg"},
    "Potassium":   {"display": "Potassium (K)",   "unit": "mg/kg"},
    "Temperature": {"display": "Temperature",     "unit": "°C"},
    "Humidity":    {"display": "Humidity",        "unit": "%"},
    "pH_Value":    {"display": "Soil pH",         "unit": ""},
    "Rainfall":    {"display": "Rainfall",        "unit": "mm/year"},
}

# ── Fertilizer boost constants (mirrored from sequential_pipeline.py) ───────────
# Applied per-season: N +40 kg/ha, P +20 kg/ha, K +15 kg/ha (converted by /2.6)
FERTILIZER_BOOST = {
    "Nitrogen":   round(40 / 2.6, 2),   # ≈ +15.38 mg/kg
    "Phosphorus": round(20 / 2.6, 2),   # ≈ +7.69 mg/kg
    "Potassium":  round(15 / 2.6, 2),   # ≈ +5.77 mg/kg
}

# ── Cached SHAP explainer (expensive to build, reused across requests) ───────
_explainer = None


def _get_explainer():
    global _explainer
    if _explainer is None:
        _explainer = shap.TreeExplainer(model)
    return _explainer


def _naive_bayes_contributions(input_df, crop_idx):
    x = input_df.to_numpy(dtype=float)[0]
    log_likelihood = -0.5 * (np.log(2 * np.pi * model.var_) + (x - model.theta_) ** 2 / model.var_)
    log_average = logsumexp(log_likelihood, axis=0, b=model.class_prior_[:, None])
    return log_likelihood[crop_idx] - log_average


def _shap_contributions(input_df, crop_idx):
    # shap_values shape for multi-class: (n_samples, n_features, n_classes)
    # or list of arrays — handle both formats tree models may return
    raw_shap = _get_explainer().shap_values(input_df)
    if isinstance(raw_shap, np.ndarray) and raw_shap.ndim == 3:
        return raw_shap[0, :, crop_idx]
    if isinstance(raw_shap, list):
        return raw_shap[crop_idx][0]
    return raw_shap[0]


def explain_prediction(data: dict, crop_name: str, display_values: dict | None = None) -> list[dict]:
    """
    Compute per-feature contributions for a specific crop prediction.

    Parameters
    ----------
    data : dict
        Feature dict with keys matching `feature_names`
        e.g. {"Nitrogen": 80, "Phosphorus": 40, ...}
    crop_name : str
        The crop to explain (must match a class in the encoder)
    display_values : dict, optional
        Values to show the user instead of the model-scale ones, e.g.
        {"Rainfall": <annual mm>} since the model sees monthly rainfall.

    Returns
    -------
    list[dict]
        Sorted by absolute contribution (most influential first).
        Empty list if crop not found in encoder or the model type isn't supported.
    """
    input_df = pd.DataFrame([data])[feature_names]

    crop_classes = list(encoder.classes_)
    try:
        crop_idx = crop_classes.index(crop_name)
    except ValueError:
        return []

    if isinstance(model, GaussianNB):
        feature_shap = _naive_bayes_contributions(input_df, crop_idx)
    elif hasattr(model, "feature_importances_"):
        feature_shap = _shap_contributions(input_df, crop_idx)
    else:
        return []

    # Total absolute mass — used to compute percentage shares
    total_abs = float(np.sum(np.abs(feature_shap))) or 1.0

    display_values = display_values or {}
    results = []
    for i, fname in enumerate(feature_names):
        contribution = float(feature_shap[i])
        abs_c = abs(contribution)
        meta = FEATURE_META.get(fname, {"display": fname, "unit": ""})
        results.append({
            "feature":          fname,
            "display_name":     meta["display"],
            "unit":             meta["unit"],
            "value":            display_values.get(fname, data[fname]),
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
