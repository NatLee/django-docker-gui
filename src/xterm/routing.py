
from django.urls import re_path
from xterm import consumers

websocket_urlpatterns = [
    re_path(r"ws/console/$", consumers.ConsoleConsumer.as_asgi()),
    re_path(r"ws/pull-image/$", consumers.PullConsumer.as_asgi()),
    re_path(r"ws/terminal/$", consumers.TerminalConsumer.as_asgi()),
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]

