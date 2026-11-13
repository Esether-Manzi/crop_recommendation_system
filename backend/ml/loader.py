import json

import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "model"

model = joblib.load(MODEL_DIR / "crop_model.pkl")
encoder = joblib.load(MODEL_DIR / "crop_encoder.pkl")
feature_names = joblib.load(MODEL_DIR / "feature_names.pkl")

# Written by `manage.py train_model`; absent for models trained before the pipeline existed.
_card_path = MODEL_DIR / "model_card.json"
model_card = json.loads(_card_path.read_text()) if _card_path.exists() else {}
model_version = model_card.get("version", "pre-pipeline")
