"""
Sequential / Next-Season Crop Recommendation Pipeline
=======================================================
Wraps the trained single-season XGBoost model (crop_model.pkl + crop_encoder.pkl)
with an agronomic nutrient-depletion engine to produce season N+1 recommendations.

How it works
------------
1. Take season-1 soil/climate features -> feed to trained model -> get Crop A.
2. Apply Crop A's nutrient depletion/fixation effect to N, P, K (pH drifts slightly;
   Temperature/Humidity/Rainfall are climate variables, assumed roughly stable
   season-to-season unless the user supplies new values).
3. Feed the UPDATED feature vector back into the SAME model -> get Crop B for next
   season. Optionally exclude Crop A (and recently-used crop family) to enforce
   rotation rather than letting the model repeat the same heavy feeder twice.
4. Repeat for as many seasons as requested.

This is "wrapping the existing classifier in a state-transition loop" rather than
training a brand-new sequential model — defensible because:
  - You do not have a real longitudinal Uganda dataset to train a true sequence
    model on (we already confirmed the India "sequential" dataset's logic is a
    positional artifact, not real agronomy - see prior analysis).
  - The nutrient depletion coefficients below come from standard agronomic
    nutrient-removal tables (FAO/IPNI-style), which is the textbook approach to
    nutrient budgeting in absence of multi-season field trial data.
  - This should be explicitly named in your report as the "rule-based sequential
    layer", with the single-season model doing the prediction and the depletion
    engine doing the state update. It is good practice to have your agronomy
    expert validators (Section 3.4.5 of your proposal) review the depletion
    coefficients table specifically.

Usage
-----
    from sequential_pipeline import recommend_sequence

    history = recommend_sequence(
        model_path="crop_model.pkl",
        encoder_path="crop_encoder.pkl",
        nutrient_table_path="Crop_Nutrient_Depletion_Table_All38.csv",  # use the 38-crop table if you retrained on the expanded Uganda dataset
        initial_features={
            "Nitrogen": 90, "Phosphorus": 42, "Potassium": 43,
            "Temperature": 20.9, "Humidity": 82.0, "pH_Value": 6.5, "Rainfall": 202.9
        },
        n_seasons=3,
        avoid_repeat_family=True,
    )
"""

import joblib
import pandas as pd
import numpy as np

FEATURE_ORDER = ["Nitrogen", "Phosphorus", "Potassium", "Temperature", "Humidity", "pH_Value", "Rainfall"]

# Topsoil conversion: kg/ha removed <-> mg/kg (~ppm) concentration change
# Standard assumption: 0-20cm depth, bulk density 1.3 t/m3 => 1 mg/kg ~ 2.6 kg/ha
CONVERSION_FACTOR = 2.6


def load_artifacts(model_path, encoder_path, nutrient_table_path):
    model = joblib.load(model_path)
    encoder = joblib.load(encoder_path)
    nutrient_table = pd.read_csv(nutrient_table_path).set_index("Crop")
    return model, encoder, nutrient_table


def apply_depletion(features: dict, crop: str, nutrient_table: pd.DataFrame, fertilizer_applied: bool = False) -> dict:
    """Return a NEW features dict representing soil state after growing `crop` one season."""
    row = nutrient_table.loc[crop]
    n_delta = (row["N_Fixation_kg_ha"] - row["N_Uptake_kg_ha"]) / CONVERSION_FACTOR
    p_delta = -row["P_Uptake_kg_ha"] / CONVERSION_FACTOR
    k_delta = -row["K_Uptake_kg_ha"] / CONVERSION_FACTOR

    if fertilizer_applied:
        n_delta += 40 / CONVERSION_FACTOR
        p_delta += 20 / CONVERSION_FACTOR
        k_delta += 15 / CONVERSION_FACTOR

    new_features = dict(features)
    new_features["Nitrogen"] = max(0, round(features["Nitrogen"] + n_delta, 2))
    new_features["Phosphorus"] = max(0, round(features["Phosphorus"] + p_delta, 2))
    new_features["Potassium"] = max(0, round(features["Potassium"] + k_delta, 2))

    ph_delta = -0.03 if row["Demand_Class"] in ["Heavy feeder", "Very heavy feeder"] else 0.01
    new_features["pH_Value"] = round(np.clip(features["pH_Value"] + ph_delta, 3.5, 8.5), 2)

    # Temperature, Humidity, Rainfall are climate variables -> left unchanged
    # unless the caller updates them between seasons (e.g. dry season vs wet season).
    return new_features


def predict_crop(model, encoder, features: dict) -> str:
    x = pd.DataFrame([[features[f] for f in FEATURE_ORDER]], columns=FEATURE_ORDER)
    pred_encoded = model.predict(x)[0]
    return encoder.inverse_transform([pred_encoded])[0]


def predict_crop_excluding(model, encoder, features: dict, exclude_crops: set) -> str:
    """
    Predict top crop, falling back to next-best-probability crop if the top
    choice is in `exclude_crops` (e.g. same crop or same family as last season).
    Requires a model that supports predict_proba (XGBClassifier does).
    """
    x = pd.DataFrame([[features[f] for f in FEATURE_ORDER]], columns=FEATURE_ORDER)
    probs = model.predict_proba(x)[0]
    ranked_idx = np.argsort(probs)[::-1]
    for idx in ranked_idx:
        crop = encoder.inverse_transform([idx])[0]
        if crop not in exclude_crops:
            return crop
    return encoder.inverse_transform([ranked_idx[0]])[0]  # fallback: top choice anyway


def recommend_sequence(model_path, encoder_path, nutrient_table_path,
                        initial_features: dict, n_seasons: int = 3,
                        avoid_repeat_family: bool = True,
                        fertilizer_schedule=None):
    """
    Returns a list of dicts, one per season:
        {season, features_before, crop_recommended, features_after}
    """
    model, encoder, nutrient_table = load_artifacts(model_path, encoder_path, nutrient_table_path)
    features = dict(initial_features)
    history = []
    used_families = set()
    exclude = set()

    for season in range(1, n_seasons + 1):
        fertilizer_applied = bool(fertilizer_schedule[season - 1]) if fertilizer_schedule else False

        if avoid_repeat_family and exclude:
            crop = predict_crop_excluding(model, encoder, features, exclude)
        else:
            crop = predict_crop(model, encoder, features)

        family = nutrient_table.loc[crop, "Family"]
        features_after = apply_depletion(features, crop, nutrient_table, fertilizer_applied)

        history.append({
            "season": season,
            "features_before": dict(features),
            "crop_recommended": crop,
            "crop_family": family,
            "fertilizer_applied": fertilizer_applied,
            "features_after": dict(features_after),
        })

        # Build exclusion set for next iteration: avoid same crop, optionally same family
        exclude = {crop}
        if avoid_repeat_family:
            same_family_crops = nutrient_table[nutrient_table["Family"] == family].index.tolist()
            exclude.update(same_family_crops)

        features = features_after

    return history


def print_sequence(history):
    for h in history:
        fb = h["features_before"]
        fa = h["features_after"]
        print(f"--- Season {h['season']} ---")
        print(f"  Soil before: N={fb['Nitrogen']}, P={fb['Phosphorus']}, K={fb['Potassium']}, pH={fb['pH_Value']}")
        print(f"  >>> Recommended crop: {h['crop_recommended']}  (family: {h['crop_family']})")
        print(f"  Fertilizer applied: {h['fertilizer_applied']}")
        print(f"  Soil after:  N={fa['Nitrogen']}, P={fa['Phosphorus']}, K={fa['Potassium']}, pH={fa['pH_Value']}")
        print()
