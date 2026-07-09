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