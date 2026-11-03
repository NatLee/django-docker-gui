"""ASGI entry point: Django for HTTP, Channels for the WebSockets in xterm/routing.py.

The WebSocket consumers log users in themselves (xterm/ws_auth.py), from the access token the
page offers as a subprotocol, so no session or cookie middleware is involved.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
# Set up Django before importing anything that touches models (the consumers do).
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from xterm.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(URLRouter(websocket_urlpatterns)),
    }
)
