from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken

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
        user = User.objects.create_user("member", password="pw")
        auth = {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(user)}"}
        for method, url in API_ENDPOINTS:
            with self.subTest(url=url), self.assertLogs("django.request", "WARNING"):
                self.assertEqual(getattr(self.client, method)(url, **auth).status_code, 401)
