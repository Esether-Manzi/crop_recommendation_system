from ml.predictor import CropPredictor
from ml.explainer import explain_prediction, get_fertilizer_boosted_inputs
from ..models import Prediction
from .suitability_service import SuitabilityService


class RecommendationService:

    @staticmethod
    def create_prediction(user, data, farm=None):

        model_input = {
            "Nitrogen": data["nitrogen"],
            "Phosphorus": data["phosphorus"],
            "Potassium": data["potassium"],
            "Temperature": data["temperature"],
            "Humidity": data["humidity"],
            "pH_Value": data["ph"],
            "Rainfall": data["rainfall"],
        }

        # Predict top 5 crops with confidence
        top_crops = CropPredictor.predict_top_n(model_input, n=5)
        top_crop = top_crops[0]["crop"]

        prediction = Prediction.objects.create(
            user=user,
            farm=farm,
            nitrogen=data["nitrogen"],
            phosphorus=data["phosphorus"],
            potassium=data["potassium"],
            temperature=data["temperature"],
            humidity=data["humidity"],
            ph=data["ph"],
            rainfall=data["rainfall"],
            predicted_crop=top_crop,
        )

        # Pre-compute fertilizer-boosted inputs once (shared across all crops)
        boosted_input = get_fertilizer_boosted_inputs(model_input)
        suitability_base_inputs = {
            "nitrogen":    data["nitrogen"],
            "phosphorus":  data["phosphorus"],
            "potassium":   data["potassium"],
            "temperature": data["temperature"],
            "humidity":    data["humidity"],
            "ph":          data["ph"],
            "rainfall":    data["rainfall"],
        }
        suitability_boosted_inputs = {
            "nitrogen":    boosted_input["Nitrogen"],
            "phosphorus":  boosted_input["Phosphorus"],
            "potassium":   boosted_input["Potassium"],
            "temperature": data["temperature"],
            "humidity":    data["humidity"],
            "ph":          data["ph"],
            "rainfall":    data["rainfall"],
        }

        recommendations = []
        for tc in top_crops:
            crop_name = tc["crop"]
            confidence = tc["confidence"]

            # ── Suitability analysis (current soil values) ──────────────────
            suitability = SuitabilityService.analyze(
                crop_name=crop_name,
                inputs=suitability_base_inputs,
            )

            # ── Suitability analysis (after fertilizer boost) ───────────────
            suitability_with_fertilizer = SuitabilityService.analyze(
                crop_name=crop_name,
                inputs=suitability_boosted_inputs,
            )

            # ── SHAP explanation — why did the model choose this crop? ──────
            explanation = explain_prediction(model_input, crop_name)

            # ── Natural-language justification sentence ──────────────────────
            reasons = []
            if suitability.get("success"):
                analysis = suitability["analysis"]
                unsuitable = [p for p, info in analysis.items() if info["status"] != "Suitable"]
                if not unsuitable:
                    reasons.append(
                        f"Perfect match! Your soil and weather are ideal for growing {crop_name.title()}."
                    )
                else:
                    reasons.append(
                        f"A good match for {crop_name.title()}, though {', '.join(unsuitable)} "
                        f"could be closer to ideal."
                    )
            else:
                reasons.append(
                    f"We don't have ideal-range data for {crop_name.title()} yet, but our AI "
                    f"still expects it to grow well here."
                )

            recommendations.append({
                "crop": crop_name,
                "confidence": confidence,
                "suitability": suitability,
                "suitability_fertilized": suitability_with_fertilizer,
                "fertilizer_boost": {
                    "Nitrogen":   boosted_input["Nitrogen"],
                    "Phosphorus": boosted_input["Phosphorus"],
                    "Potassium":  boosted_input["Potassium"],
                },
                "explanation": explanation,
                "reasons": reasons,
            })

        return {
            "prediction": prediction,
            "recommendations": recommendations,
        }
