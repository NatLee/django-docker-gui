import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from backend.settings import env_flag, env_list

SRC_DIR = Path(__file__).resolve().parents[2]

PRINT_SETTINGS = (
    "import django; django.setup(); from django.conf import settings as s; "
    "print(s.DEBUG, ','.join(s.ALLOWED_HOSTS), s.REDIS_URL)"
)


def load_settings(**env):
    """Load the settings in a fresh interpreter with exactly these DJANGO_*/REDIS_URL variables."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_") and k != "REDIS_URL"}
    clean.update(DJANGO_SETTINGS_MODULE="backend.settings", **env)
    return subprocess.run(
        [sys.executable, "-c", PRINT_SETTINGS], cwd=SRC_DIR, env=clean, capture_output=True, text=True
    )


class SettingsFromEnvironmentTests(SimpleTestCase):
    def test_refuses_to_load_without_a_secret_key(self):
        result = load_settings()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY is not set", result.stderr)

    def test_blank_secret_key_counts_as_missing(self):
        result = load_settings(DJANGO_SECRET_KEY="   ")
        self.assertIn("DJANGO_SECRET_KEY is not set", result.stderr)

    def test_debug_is_off_and_any_host_allowed_by_default(self):
        result = load_settings(DJANGO_SECRET_KEY="x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split()[-3:], ["False", "*", "redis://redis:6379"])

    def test_debug_hosts_and_redis_come_from_the_environment(self):
        result = load_settings(
            DJANGO_SECRET_KEY="x", DJANGO_DEBUG="yes", DJANGO_ALLOWED_HOSTS="localhost, 10.0.0.2,",
            REDIS_URL="redis://cache:6380/1",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split()[-3:], ["True", "localhost,10.0.0.2", "redis://cache:6380/1"])


class EnvHelperTests(SimpleTestCase):
    def test_env_flag(self):
        for value, expected in [("1", True), ("TRUE", True), (" on ", True), ("yes", True),
                                ("0", False), ("false", False), ("", False), ("maybe", False)]:
            with self.subTest(value=value), mock.patch.dict(os.environ, FLAG=value):
                self.assertIs(env_flag("FLAG"), expected)
        with mock.patch.dict(os.environ):
            os.environ.pop("FLAG", None)
            self.assertIs(env_flag("FLAG"), False)
            self.assertIs(env_flag("FLAG", default=True), True)

    def test_env_list(self):
        with mock.patch.dict(os.environ, ITEMS=" a, b ,,c "):
            self.assertEqual(env_list("ITEMS"), ["a", "b", "c"])
        with mock.patch.dict(os.environ):
            os.environ.pop("ITEMS", None)
            self.assertEqual(env_list("ITEMS", "*"), ["*"])
            self.assertEqual(env_list("ITEMS"), [])


class ChannelLayerTests(SimpleTestCase):
    def test_redis_reads_wait_longer_than_the_channel_layer_blocks(self):
        from channels_redis.core import RedisChannelLayer
        from channels_redis.utils import create_pool
        from django.conf import settings

        config = settings.CHANNEL_LAYERS["default"]["CONFIG"]
        pool = create_pool(dict(config["hosts"][0]))
        timeout = pool.connection_class(**pool.connection_kwargs).socket_timeout  # does not connect
        self.assertTrue(timeout is None or timeout > RedisChannelLayer.brpop_timeout, timeout)
