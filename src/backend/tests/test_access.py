"""The owner's rule (2026-11-04): the whole app is for active superusers only, enforced in one place
(backend/access.py). The REST API and the WebSockets are also covered in xterm/tests."""
from django.contrib.auth.models import AnonymousUser, User
from django.test import SimpleTestCase, TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import TokenViewBase

from backend.access import LOGIN_REFUSED, SUPERUSERS_ONLY, SuperusersOnly, may_use_app


def drf_views(patterns=None, prefix=""):
    """(url, view class) for every DRF view in the URLconf."""
    for entry in get_resolver().url_patterns if patterns is None else patterns:
        if isinstance(entry, URLResolver):
            yield from drf_views(entry.url_patterns, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern):
            cls = getattr(entry.callback, "cls", None)
            if isinstance(cls, type) and issubclass(cls, APIView):
                yield prefix + str(entry.pattern), cls


def post_json(client, url, data):
    return client.post(url, data, content_type="application/json")


class RuleTests(SimpleTestCase):
    def test_only_active_superusers(self):
        cases = [
            (None, False),
            (AnonymousUser(), False),
            (User(is_active=True), False),
            (User(is_active=True, is_staff=True), False),
            (User(is_active=False, is_superuser=True, is_staff=True), False),
            (User(is_active=True, is_superuser=True), True),
        ]
        for user, expected in cases:
            with self.subTest(user=user):
                self.assertIs(may_use_app(user), expected)

    def test_it_is_the_default_for_every_api_view_and_no_view_sets_its_own(self):
        self.assertEqual(api_settings.DEFAULT_PERMISSION_CLASSES, [SuperusersOnly])
        views = list(drf_views())
        self.assertGreater(len(views), 10)
        for url, cls in views:
            with self.subTest(url=url):
                if issubclass(cls, TokenViewBase):  # the login views: the rule runs inside (LoginTests)
                    continue
                self.assertEqual(list(cls.permission_classes), [SuperusersOnly])


class LoginTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="pw")
        User.objects.create_user("member", password="pw")
        User.objects.create_user("staff", password="pw", is_staff=True)

    def login(self, username, password="pw"):
        return post_json(self.client, "/api/auth/token", {"username": username, "password": password})

    def test_superusers_get_tokens(self):
        self.assertEqual(set(self.login("admin").json()), {"access_token", "refresh_token"})

    def test_others_get_the_same_answer_as_a_wrong_password(self):
        with self.assertLogs("django.request", "WARNING"):
            answers = [self.login("member"), self.login("staff"), self.login("admin", "wrong")]
        for response in answers:
            self.assertEqual(response.status_code, 401)
            # The same text for all three, so the answer doesn't reveal that a password was right.
            self.assertEqual(response.json()["detail"], LOGIN_REFUSED)
        self.assertIn("superusers only", LOGIN_REFUSED)

    def test_refresh_and_verify_stop_when_superuser_is_taken_away(self):
        tokens = self.login("admin").json()
        User.objects.filter(pk=self.admin.pk).update(is_superuser=False)
        with self.assertLogs("django.request", "WARNING"):
            refresh = post_json(self.client, "/api/auth/token/refresh", {"refresh": tokens["refresh_token"]})
            verify = post_json(self.client, "/api/auth/token/verify", {"token": tokens["access_token"]})
        self.assertEqual(refresh.status_code, 401)
        self.assertEqual(refresh.json()["detail"], SUPERUSERS_ONLY)
        self.assertEqual(verify.status_code, 401)
        self.assertEqual(verify.json(), {"detail": SUPERUSERS_ONLY, "code": "superusers_only"})

    def test_verify_accepts_a_superuser(self):
        token = str(AccessToken.for_user(self.admin))
        self.assertEqual(post_json(self.client, "/api/auth/token/verify", {"token": token}).status_code, 200)

    def test_a_non_superusers_refresh_token_gets_nothing(self):
        member = User.objects.get(username="member")
        with self.assertLogs("django.request", "WARNING"):
            response = post_json(self.client, "/api/auth/token/refresh", {"refresh": str(RefreshToken.for_user(member))})
        self.assertEqual(response.status_code, 401)


class AdminPagesTests(TestCase):
    """Django admin, the RQ pages and the API docs: superusers only, a staff account isn't enough."""

    ADMIN_PAGES = ["/api/__hidden_admin/", "/api/__django-rq/"]  # redirect to the admin login
    API_DOCS = ["/api/__hidden_swagger", "/api/__hidden_redoc"]  # answer 403

    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="pw")
        self.staff = User.objects.create_user("staff", password="pw", is_staff=True)

    def test_staff_is_not_enough(self):
        self.client.force_login(self.staff)
        for url in self.ADMIN_PAGES:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/api/__hidden_admin/login/", response["Location"])
        for url in self.API_DOCS:
            with self.subTest(url=url), self.assertLogs("django.request", "WARNING"):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_login_says_why(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get("/api/__hidden_admin/login/"), "not authorized to access this page")

    def test_superusers_get_in(self):
        # The RQ dashboard needs Redis, so a superuser opening it is checked in xterm/tests/test_live.py.
        self.client.force_login(self.admin)
        for url in ["/api/__hidden_admin/"] + self.API_DOCS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
