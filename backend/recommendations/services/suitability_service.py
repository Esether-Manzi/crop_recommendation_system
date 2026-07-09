from pathlib import Path

import pandas as pd


class SuitabilityService:
    """
    Analyzes whether the user's environmental and soil values
    fall within the ideal suitability ranges for a predicted crop.
    """

    _dataset = None

    DATASET_PATH = (
        Path(__file__).resolve()
        .parents[2]
        / "ml"
        / "datasets"
        / "Uganda_Crop_Suitability_Ranges.csv"
    )

    @classmethod
    def _load_dataset(cls):
        """
        Load the CSV only once.
        """
        if cls._dataset is None:
            cls._dataset = pd.read_csv(cls.DATASET_PATH)

        return cls._dataset

    @staticmethod
    def _evaluate(value, minimum, maximum):
        """
        Compare a value against an acceptable range.
        """

        if value < minimum:
            return "Too Low"

        if value > maximum:
            return "Too High"

        return "Suitable"

    @classmethod
    def analyze(cls, crop_name, inputs):
        """
        Parameters
        ----------
        crop_name : str
            Predicted crop.

        inputs : dict
            Example:
            {
                "nitrogen": 80,
                "phosphorus": 40,
                "potassium": 60,
                "temperature": 25,
                "humidity": 80,
                "ph": 6.5,
                "rainfall": 1200
            }

        Returns
        -------
        dict
        """

        dataset = cls._load_dataset()

        crop = dataset[
            dataset["Crop"].str.lower() == crop_name.lower()
        ]

        if crop.empty:
            return {
                "success": False,
                "message": f"No suitability data found for '{crop_name}'."
            }

        crop = crop.iloc[0]

        analysis = {
            "Nitrogen": {
                "current": inputs["nitrogen"],
                "ideal": f"{crop['N_min']} - {crop['N_max']}",
                "status": cls._evaluate(
                    inputs["nitrogen"],
                    crop["N_min"],
                    crop["N_max"],
                ),
            },

            "Phosphorus": {
                "current": inputs["phosphorus"],
                "ideal": f"{crop['P_min']} - {crop['P_max']}",
                "status": cls._evaluate(
                    inputs["phosphorus"],
                    crop["P_min"],
                    crop["P_max"],
                ),
            },

            "Potassium": {
                "current": inputs["potassium"],
                "ideal": f"{crop['K_min']} - {crop['K_max']}",
                "status": cls._evaluate(
                    inputs["potassium"],
                    crop["K_min"],
                    crop["K_max"],
                ),
            },

            "Temperature": {
                "current": inputs["temperature"],
                "ideal": f"{crop['Temp_min']} - {crop['Temp_max']} °C",
                "status": cls._evaluate(
                    inputs["temperature"],
                    crop["Temp_min"],
                    crop["Temp_max"],
                ),
            },

            "Humidity": {
                "current": inputs["humidity"],
                "ideal": f"{crop['Hum_min']} - {crop['Hum_max']} %",
                "status": cls._evaluate(
                    inputs["humidity"],
                    crop["Hum_min"],
                    crop["Hum_max"],
                ),
            },

            "Soil pH": {
                "current": inputs["ph"],
                "ideal": f"{crop['pH_min']} - {crop['pH_max']}",
                "status": cls._evaluate(
                    inputs["ph"],
                    crop["pH_min"],
                    crop["pH_max"],
                ),
            },

            "Rainfall": {
                "current": inputs["rainfall"],
                "ideal": f"{crop['Rain_min']} - {crop['Rain_max']} mm",
                "status": cls._evaluate(
                    inputs["rainfall"],
                    crop["Rain_min"],
                    crop["Rain_max"],
                ),
            },
        }

        suitable = sum(
            1
            for item in analysis.values()
            if item["status"] == "Suitable"
        )

        total = len(analysis)

        return {
            "success": True,
            "crop": crop_name,
            "category": crop["Category"],
            "score": suitable,
            "total": total,
            "percentage": round((suitable / total) * 100, 1),
            "analysis": analysis,
        }