from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from backend.access import SUPERUSERS_ONLY

# Every Docker API route. Auth runs before the view, so no Docker daemon is needed here.
API_ENDPOINTS = [
    ("get", "/api/containers"),
    ("get", "/api/images"),
    ("get", "/api/browse?q=nginx"),
    ("get", "/api/console/shell/abc"),
    ("post", "/api/images/run"),
    ("post", "/api/images/remove"),
    ("post", "/api/containers/start-stop-remove"),
]


class ApiLoginTests(TestCase):
    def test_every_docker_endpoint_needs_a_login(self):
        for method, url in API_ENDPOINTS:
            with self.subTest(url=url), self.assertLogs("django.request", "WARNING"):
                self.assertEqual(getattr(self.client, method)(url).status_code, 401)

    def test_refresh_token_is_not_an_access_token(self):
        user = User.objects.create_superuser("admin", password="pw")
        auth = {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(user)}"}
        for method, url in API_ENDPOINTS:
            with self.subTest(url=url), self.assertLogs("django.request", "WARNING"):
                self.assertEqual(getattr(self.client, method)(url, **auth).status_code, 401)

    def test_every_docker_endpoint_refuses_non_superusers_with_a_reason(self):
        # The owner's rule (backend/access.py): superusers only, staff accounts included in "no".
        for name, extra in (("member", {}), ("staff", {"is_staff": True})):
            user = User.objects.create_user(name, password="pw", **extra)
            auth = {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(user)}"}
            for method, url in API_ENDPOINTS:
                with self.subTest(user=name, url=url), self.assertLogs("django.request", "WARNING"):
                    response = getattr(self.client, method)(url, **auth)
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(response.json()["detail"], SUPERUSERS_ONLY)
