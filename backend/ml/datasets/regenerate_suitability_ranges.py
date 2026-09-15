"""
One-off regenerator for Uganda_Crop_Suitability_Ranges.csv.

The suitability ranges used to be hand-authored independently of the model's
training data (Uganda_Expanded_Crop_Recommendation_Dataset.csv), so the two
disagreed on what "ideal" meant for a given feature - most severely for
Rainfall, where 22 of 38 crops had zero overlap between the two datasets'
ranges. That let the UI tell a farmer their rainfall was "Too Low" for a
crop the model was simultaneously recommending with high confidence.

This script derives each crop's ideal range directly from the training
data's actual min/max per feature, rounded outward to a clean display step,
so the suitability display can never contradict what the model itself
learned. Category (Cereal/Legume/etc.) is metadata not present in the
training data, so it's carried over from the existing CSV unchanged.

Not part of the app - run manually if the model is retrained on different
data, then discard.
"""
import math
import pandas as pd

TRAIN_PATH = "ml/datasets/Uganda_Expanded_Crop_Recommendation_Dataset.csv"
SUIT_PATH = "ml/datasets/Uganda_Crop_Suitability_Ranges.csv"

# (train column, display min column, display max column, round-to step)
FEATURES = [
    ("Nitrogen", "N_min", "N_max", 5),
    ("Phosphorus", "P_min", "P_max", 5),
    ("Potassium", "K_min", "K_max", 5),
    ("Temperature", "Temp_min", "Temp_max", 1),
    ("Humidity", "Hum_min", "Hum_max", 5),
    ("pH_Value", "pH_min", "pH_max", 0.1),
    ("Rainfall", "Rain_min", "Rain_max", 50),
]


def floor_to(value, step):
    result = math.floor(value / step) * step
    return round(result, 1) if step < 1 else int(result)


def ceil_to(value, step):
    result = math.ceil(value / step) * step
    return round(result, 1) if step < 1 else int(result)


train = pd.read_csv(TRAIN_PATH)
suit = pd.read_csv(SUIT_PATH)
categories = dict(zip(suit["Crop"], suit["Category"]))

rows = []
for crop, group in train.groupby("Crop"):
    row = {"Crop": crop}
    for train_col, min_col, max_col, step in FEATURES:
        row[min_col] = floor_to(group[train_col].min(), step)
        row[max_col] = ceil_to(group[train_col].max(), step)
    row["Category"] = categories[crop]
    rows.append(row)

# Preserve the original crop ordering rather than groupby's alphabetical one.
order = {crop: i for i, crop in enumerate(suit["Crop"])}
rows.sort(key=lambda r: order[r["Crop"]])

columns = ["Crop"] + [c for _, min_c, max_c, _ in FEATURES for c in (min_c, max_c)] + ["Category"]
out = pd.DataFrame(rows, columns=columns)
out.to_csv(SUIT_PATH, index=False)

print(f"Regenerated {len(out)} crop ranges from training data.")
