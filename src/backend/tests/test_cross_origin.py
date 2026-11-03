from django.test import TestCase


class CrossOriginTests(TestCase):
    """The pages and the API are served from one origin, so other sites get no CORS grant."""

    def test_api_does_not_grant_other_origins(self):
        response = self.client.get("/api/containers", HTTP_ORIGIN="https://evil.example")
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        self.assertNotIn("Access-Control-Allow-Credentials", response.headers)

    def test_preflight_is_not_answered_with_a_grant(self):
        response = self.client.options(
            "/api/containers/start-stop-remove",
            HTTP_ORIGIN="https://evil.example",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
