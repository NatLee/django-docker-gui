import base64

from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken

from backend.asgi import application

IN_MEMORY_LAYER = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


def token_protocol(token: str, padded: bool = False) -> str:
    encoded = base64.b64encode(token.encode()).decode()
    return "token." + (encoded if padded else encoded.rstrip("="))


def access_token(user) -> str:
    return str(AccessToken.for_user(user))


def communicator(path: str, protocols=()):
    return WebsocketCommunicator(application, path, subprotocols=list(protocols))


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYER)
class ConsumerTestCase(TransactionTestCase):
    """Consumers look users up from another thread, so the test data has to be committed."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="pw")
        self.member = User.objects.create_user("member", password="pw")

    def protocols(self, user, name="test"):
        return [name, token_protocol(access_token(user))]
