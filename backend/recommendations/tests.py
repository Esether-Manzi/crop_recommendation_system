from datetime import date, timedelta

from django.test import SimpleTestCase

from ml.input_checks import HARD_LIMITS, check_inputs, check_soil_test, training_ranges

from .forms import PredictionForm

# Typical Ugandan maize field, inside every range the model learned from.
MAIZE = {"nitrogen": 80, "phosphorus": 45, "potassium": 20, "temperature": 22, "humidity": 65, "ph": 6.2, "rainfall": 1000}


def codes(warnings):
    return [w["code"] for w in warnings]


class InputChecksTests(SimpleTestCase):
    def test_typical_values_raise_no_warnings(self):
        self.assertEqual(check_inputs(MAIZE), [])

    def test_nutrient_below_one_is_flagged_as_unit_mistake(self):
        warnings = check_inputs({**MAIZE, "nitrogen": 0.15})
        self.assertIn("unit", codes(warnings))
        self.assertEqual(warnings[0]["field"], "nitrogen")

    def test_monthly_rainfall_is_flagged(self):
        warnings = check_inputs({**MAIZE, "rainfall": 90})
        self.assertIn("rainfall", [w["field"] for w in warnings if w["code"] == "unit"])

    def test_value_outside_training_data_is_flagged(self):
        low, high = training_ranges()["potassium"]
        warnings = check_inputs({**MAIZE, "potassium": high + 50})
        self.assertIn("potassium", [w["field"] for w in warnings if w["code"] == "outside_training_range"])

    def test_soil_unlike_any_crop_is_flagged(self):
        # Each value is individually plausible, but no crop has this combination.
        odd = {"nitrogen": 190, "phosphorus": 5, "potassium": 280, "temperature": 12, "humidity": 20, "ph": 8.4, "rainfall": 3500}
        self.assertIn("unusual_soil", codes(check_inputs(odd)))

    def test_typo_in_one_value_is_flagged_as_unusual(self):
        self.assertIn("unusual_soil", codes(check_inputs({**MAIZE, "nitrogen": 800})))

    def test_soil_where_every_feature_argues_against_the_top_crop_is_flagged(self):
        # Step-1 sweep case: Coffee came out on top with every explanation bar negative.
        soil = {"nitrogen": 80, "phosphorus": 40, "potassium": 40, "temperature": 24, "humidity": 70, "ph": 6.0, "rainfall": 1200}
        self.assertIn("unusual_soil", codes(check_inputs(soil)))

    def test_rainfall_ranges_are_annual(self):
        low, high = training_ranges()["rainfall"]
        self.assertGreater(high, 1000)


class SoilTestChecksTests(SimpleTestCase):
    def test_recent_lab_test_is_fine(self):
        self.assertEqual(check_soil_test("lab", date.today() - timedelta(days=200)), [])

    def test_old_test_is_flagged(self):
        self.assertIn("old_test", codes(check_soil_test("lab", date.today() - timedelta(days=4 * 365))))

    def test_estimate_and_simulated_are_flagged(self):
        self.assertIn("estimated", codes(check_soil_test("estimate", None)))
        self.assertIn("simulated", codes(check_soil_test("simulated", None)))


class PredictionFormTests(SimpleTestCase):
    def test_accepts_typical_values(self):
        self.assertTrue(PredictionForm(data=MAIZE).is_valid())

    def test_rejects_values_beyond_hard_limits(self):
        for field, (low, high) in HARD_LIMITS.items():
            with self.subTest(field=field):
                form = PredictionForm(data={**MAIZE, field: high + 1})
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_accepts_decimal_nutrients(self):
        self.assertTrue(PredictionForm(data={**MAIZE, "nitrogen": 0.15}).is_valid())
