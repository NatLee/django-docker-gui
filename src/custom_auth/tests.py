from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from google.auth.exceptions import GoogleAuthError
from rest_framework_simplejwt.tokens import AccessToken

from custom_auth.models import SocialAccount

URL = "/api/auth/google/token"
CLAIMS = {"sub": "google-123", "email": "ana@example.org", "email_verified": True,
          "given_name": "Ana", "family_name": "Lee"}


def google_says(claims=None, error=None):
    return mock.patch("custom_auth.serializers.id_token.verify_oauth2_token",
                      side_effect=error, return_value=claims)


class GoogleSignInTests(TestCase):
    def post(self):
        return self.client.post(URL, {"credential": "a-google-id-token"}, content_type="application/json")

    def test_off_unless_a_client_id_is_configured(self):
        with google_says(CLAIMS) as verify, self.assertLogs("django.request", "WARNING"):
            self.assertEqual(self.post().status_code, 404)
        verify.assert_not_called()
        self.assertFalse(User.objects.exists())

    @override_settings(SOCIAL_GOOGLE_CLIENT_ID="cid", VALID_REGISTER_DOMAINS=["example.org"])
    def test_allowed_domain_signs_up_once_then_logs_in(self):
        with google_says(CLAIMS) as verify, self.assertLogs("custom_auth", "INFO"):
            first = self.post()
            second = self.post()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(verify.call_args.args[2], "cid")  # checked against our client ID
        user = User.objects.get()
        self.assertEqual((user.username, user.email, user.first_name), ("ana", "ana@example.org", "Ana"))
        self.assertEqual(SocialAccount.objects.get().user, user)
        self.assertEqual(AccessToken(second.json()["access_token"])["user_id"], str(user.id))

    @override_settings(SOCIAL_GOOGLE_CLIENT_ID="cid", VALID_REGISTER_DOMAINS=[])
    def test_nobody_may_sign_up_by_default(self):
        with google_says(CLAIMS), self.assertLogs("custom_auth", "WARNING"), self.assertLogs("django.request", "WARNING"):
            self.assertEqual(self.post().status_code, 401)
        self.assertFalse(User.objects.exists())

    @override_settings(SOCIAL_GOOGLE_CLIENT_ID="cid", VALID_REGISTER_DOMAINS=["example.org"])
    def test_other_domains_and_unverified_addresses_are_refused(self):
        for claims in ({**CLAIMS, "email": "eve@example.org.evil.com"}, {**CLAIMS, "email_verified": False}):
            with self.subTest(claims=claims), google_says(claims), \
                    self.assertLogs("custom_auth", "WARNING"), self.assertLogs("django.request", "WARNING"):
                self.assertEqual(self.post().status_code, 401)
        self.assertFalse(User.objects.exists())

    @override_settings(SOCIAL_GOOGLE_CLIENT_ID="cid", VALID_REGISTER_DOMAINS=["example.org"])
    def test_bad_google_tokens_are_401_not_500(self):
        for error in (ValueError("Token expired"), GoogleAuthError("Wrong issuer")):
            with self.subTest(error=error), google_says(error=error), \
                    self.assertLogs("custom_auth", "WARNING"), self.assertLogs("django.request", "WARNING"):
                self.assertEqual(self.post().status_code, 401)
