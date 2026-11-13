from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from farms.models import Farm, SoilRecord


class DashboardLatestSoilTests(TestCase):
    def test_latest_soil_is_newest_record_across_all_farms(self):
        user = User.objects.create_user("farmer", "farmer@example.test", "x-Test-pass-91")
        soil = dict(nitrogen=50, phosphorus=40, potassium=40, ph=6.5, temperature=22, humidity=70, rainfall=1000)
        farm_a = Farm.objects.create(user=user, farm_name="Farm A", district="X", subcounty="Y", size_acres=1)
        farm_b = Farm.objects.create(user=user, farm_name="Farm B", district="X", subcounty="Y", size_acres=1)

        older = SoilRecord.objects.create(farm=farm_b, **soil)
        SoilRecord.objects.filter(pk=older.pk).update(recorded_at=timezone.now() - timedelta(days=30))
        newest = SoilRecord.objects.create(farm=farm_a, **soil)

        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.context["latest_soil"], newest)
