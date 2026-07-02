from django.test import TestCase
from django.urls import reverse


class LoginPageTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")
        self.assertContains(response, "Welcome back")
