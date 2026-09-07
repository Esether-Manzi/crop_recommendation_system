import pandas as pd

from .loader import model, encoder, feature_names


class CropPredictor:

    @staticmethod
    def predict(data: dict):

        input_df = pd.DataFrame([data])

        input_df = input_df[feature_names]

        prediction = model.predict(input_df)[0]

        crop = encoder.inverse_transform([prediction])[0]

        return crop

    @staticmethod
    def predict_top_n(data: dict, n: int = 5):
        input_df = pd.DataFrame([data])
        input_df = input_df[feature_names]

        # Use predict_proba to get probabilities
        probs = model.predict_proba(input_df)[0]
        top_indices = probs.argsort()[::-1][:n]

        results = []
        for idx in top_indices:
            crop_name = encoder.inverse_transform([idx])[0]
            confidence = float(probs[idx])
            results.append({
                "crop": crop_name,
                "confidence": round(confidence * 100, 1),
            })
        return results