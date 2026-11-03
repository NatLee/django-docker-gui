import importlib.util

from django.apps import apps
from django.conf import settings
from django.test import TestCase


class GoogleLoginRemovedTests(TestCase):
    """The user decided on 2026-11-04 to drop Google sign-in completely, switches included."""

    def test_endpoint_is_gone(self):
        with self.assertLogs("django.request", "WARNING"):
            response = self.client.post("/api/auth/google/token", {"credential": "x"}, content_type="application/json")
        self.assertEqual(response.status_code, 404)

    def test_app_settings_and_package_are_gone(self):
        self.assertFalse(apps.is_installed("custom_auth"))
        self.assertEqual([name for name in dir(settings) if "GOOGLE" in name or "SOCIAL" in name], [])
        self.assertIsNone(importlib.util.find_spec("google"))  # google-auth was the only "google" package
