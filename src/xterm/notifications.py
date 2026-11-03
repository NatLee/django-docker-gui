"""Messages to every open Containers and Images page, over the notifications WebSocket.

A message is {"action": <event>, "details": <text for the toast>} plus, for WAITING, "data".
Events: WAITING (a job was queued), CREATED, STARTED, STOPPED, RESTARTED, REMOVED (a job
finished) and FAILED (a job did not finish; the page shows the reason and reloads its list).
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

GROUP = "group_notifications"


def notify(action: str, details: str, data: dict | None = None) -> None:
    message = {"action": action, "details": details}
    if data is not None:
        message["data"] = data
    async_to_sync(get_channel_layer().group_send)(GROUP, {"type": "send_notification", "message": message})
