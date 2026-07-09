import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "model"

model = joblib.load(MODEL_DIR / "crop_model.pkl")
encoder = joblib.load(MODEL_DIR / "crop_encoder.pkl")
feature_names = joblib.load(MODEL_DIR / "feature_names.pkl")