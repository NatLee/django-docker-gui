from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken


class TokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="1234")

    def post(self, url, data):
        return self.client.post(url, data, content_type="application/json")

    def test_login_refresh_and_verify(self):
        tokens = self.post("/api/auth/token", {"username": "admin", "password": "1234"}).json()
        self.assertEqual(set(tokens), {"access_token", "refresh_token"})
        self.assertEqual(AccessToken(tokens["access_token"])["user_id"], str(self.user.id))

        refreshed = self.post("/api/auth/token/refresh", {"refresh": tokens["refresh_token"]}).json()
        self.assertEqual(set(refreshed), {"access_token"})
        self.assertEqual(self.post("/api/auth/token/verify", {"token": refreshed["access_token"]}).status_code, 200)

    def test_wrong_password_is_401(self):
        with self.assertLogs("django.request", "WARNING"):
            response = self.post("/api/auth/token", {"username": "admin", "password": "nope"})
        self.assertEqual(response.status_code, 401)
