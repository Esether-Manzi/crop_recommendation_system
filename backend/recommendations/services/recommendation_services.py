from ml.predictor import CropPredictor
from ..models import Prediction
from .suitability_service import SuitabilityService

class RecommendationService:

    @staticmethod
    def create_prediction(user, data):

        model_input = {
            "Nitrogen": data["nitrogen"],
            "Phosphorus": data["phosphorus"],
            "Potassium": data["potassium"],
            "Temperature": data["temperature"],
            "Humidity": data["humidity"],
            "pH_Value": data["ph"],
            "Rainfall": data["rainfall"],
        }

        predicted_crop = CropPredictor.predict(model_input)

        prediction = Prediction.objects.create(
            user=user,
            nitrogen=data["nitrogen"],
            phosphorus=data["phosphorus"],
            potassium=data["potassium"],
            temperature=data["temperature"],
            humidity=data["humidity"],
            ph=data["ph"],
            rainfall=data["rainfall"],
            predicted_crop=predicted_crop,
        )

        report = SuitabilityService.analyze(
            crop_name=predicted_crop,
            inputs={
                "nitrogen": data["nitrogen"],
                "phosphorus": data["phosphorus"],
                "potassium": data["potassium"],
                "temperature": data["temperature"],
                "humidity": data["humidity"],
                "ph": data["ph"],
                "rainfall": data["rainfall"],
            }
        )

        return {
            "prediction": prediction,
            "suitability": report,
        }