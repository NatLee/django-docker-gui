"""WebSocket consumers: container console and attach, host terminal, image pulls, notifications."""
import asyncio
import json
import logging
from typing import Callable, Optional

import docker
from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer

from xterm.permissions import can_manage_docker, can_open_host_shell
from xterm.terminal import ContainerAttach, ContainerShell, ContainerUnavailable, HostShell, OutputDecoder
from xterm.ws_auth import read_subprotocols, user_for_token

logger = logging.getLogger(__name__)

# Close codes. The first two are sent before the handshake is accepted (the browser sees a
# refused connection); the others end an accepted connection.
CLOSE_NOT_LOGGED_IN = 4001
CLOSE_FORBIDDEN = 4002
CLOSE_CONTAINER_UNAVAILABLE = 4004
CLOSE_SHELL_FAILED = 4005


def parse_message(text_data: Optional[str]) -> tuple[Optional[str], dict]:
    """`{"action": ..., "payload": {...}}` -> (action, payload); (None, {}) for anything else."""
    try:
        message = json.loads(text_data or "")
    except ValueError:
        return None, {}
    if not isinstance(message, dict):
        return None, {}
    payload = message.get("payload")
    return message.get("action"), payload if isinstance(payload, dict) else {}


class AuthenticatedConsumer(AsyncWebsocketConsumer):
    """Accepts a connection only from a logged-in user that `allowed()` lets in."""

    user = None

    def allowed(self, user) -> bool:
        return can_manage_docker(user)

    async def connect(self):
        offered = read_subprotocols(self.scope.get("subprotocols"))
        user = await user_for_token(offered.token)
        if user is None:
            logger.warning("%s refused: no valid access token", self.scope["path"])
            await self.close(code=CLOSE_NOT_LOGGED_IN)
            return
        if not self.allowed(user):
            logger.warning("%s refused for %s: not allowed", self.scope["path"], user)
            await self.close(code=CLOSE_FORBIDDEN)
            return
        self.user = user
        await self.accept(offered.accept_with)
        await self.connected()

    async def connected(self):
        """Runs once the handshake is accepted."""


class TerminalSessionConsumer(AuthenticatedConsumer):
    """Connects one WebSocket to one session from xterm.terminal.

    Messages from the page: `pty_input` with `{"input": "<text>"}` and `pty_resize` with
    `{"size": {"rows", "cols", "width", "height"}}`. Everything the session prints goes back as
    text frames, in order. The connection closes when the session ends, and the session is
    closed when the connection does.
    """

    session = None
    fd = None

    async def start_session(self, open_session: Callable[[], object]):
        try:
            self.session = await asyncio.to_thread(open_session)
        except ContainerUnavailable as exc:
            logger.info("%s: %s", self.scope["path"], exc)
            await self.close(code=CLOSE_CONTAINER_UNAVAILABLE)
            return
        except (docker.errors.APIError, OSError) as exc:
            logger.error("%s: could not start the session: %s", self.scope["path"], exc)
            await self.close(code=CLOSE_SHELL_FAILED)
            return
        self.decoder = OutputDecoder(self.session.multiplexed)
        self.outbox: asyncio.Queue = asyncio.Queue()
        self.sender = asyncio.create_task(self.send_output())
        self.fd = self.session.fileno()
        asyncio.get_running_loop().add_reader(self.fd, self.read_output)

    def read_output(self):
        """Called by the event loop whenever the session has something to read."""
        try:
            data = self.session.read()
        except OSError:
            data = b""
        if data is None:  # woke up without data
            return
        if not data:
            self.stop_reading()
            self.outbox.put_nowait(None)
            return
        text = self.decoder.feed(data)
        if text:
            self.outbox.put_nowait(text)

    async def send_output(self):
        while (text := await self.outbox.get()) is not None:
            await self.send(text_data=text)
        await self.close()  # the session ended (shell exited, container stopped)

    def stop_reading(self):
        if self.fd is not None:
            asyncio.get_running_loop().remove_reader(self.fd)
            self.fd = None

    async def receive(self, text_data=None, bytes_data=None):
        action, payload = parse_message(text_data)
        if self.session is None:
            await self.before_session(action, payload)
        elif action == "pty_input" and isinstance(payload.get("input"), str):
            await self.call_session(self.session.write, payload["input"].encode())
        elif action == "pty_resize":
            size = terminal_size(payload.get("size"))
            if size:
                await self.call_session(self.session.resize, *size)

    async def call_session(self, method, *args):
        """Run a (blocking) session call off the event loop; a broken session ends the connection."""
        try:
            await asyncio.to_thread(method, *args)
        except (OSError, docker.errors.APIError) as exc:
            logger.warning("%s: %s failed: %s", self.scope["path"], method.__name__, exc)
            await self.close()

    async def before_session(self, action: Optional[str], payload: dict):
        """Messages that arrive before a session exists (the console picks its session here)."""

    async def disconnect(self, code):
        session, self.session = self.session, None
        if session is None:
            return
        self.stop_reading()
        self.sender.cancel()
        await asyncio.to_thread(session.close)


def terminal_size(size) -> Optional[tuple[int, int, int, int]]:
    """(rows, cols, width, height) from a `pty_resize` payload, or None if rows/cols are missing."""
    if not isinstance(size, dict):
        return None
    try:
        rows, cols = int(size["rows"]), int(size["cols"])
        width, height = int(size.get("width") or 0), int(size.get("height") or 0)
    except (KeyError, TypeError, ValueError):
        return None
    if rows <= 0 or cols <= 0:
        return None
    return rows, cols, max(width, 0), max(height, 0)


class ConsoleConsumer(TerminalSessionConsumer):
    """Console and Attach on the Containers page. The first message picks the session:
    `shell` or `attach` with `{"Id": "<container id>"}`."""

    SESSIONS = {"shell": ContainerShell, "attach": ContainerAttach}

    async def before_session(self, action, payload):
        session_class = self.SESSIONS.get(action)
        container_id = payload.get("Id")
        if session_class and isinstance(container_id, str) and container_id:
            await self.start_session(lambda: session_class.open(container_id))


class TerminalConsumer(TerminalSessionConsumer):
    """The Terminal page: bash inside this app's own container, for superusers."""

    def allowed(self, user) -> bool:
        return can_open_host_shell(user)

    async def connected(self):
        await self.start_session(HostShell)


class PullConsumer(AuthenticatedConsumer):
    async def receive(self, text_data):
        message = json.loads(text_data)
        # Route message to appropriate handler
        action = message.get('action')
        payload = message.get('payload')
        if action == 'pull_image':
            image_name = payload.get('image', '')
            image_version = payload.get('version', 'lastest')
            if image_name and image_version:
                await self.pull_image_input(image_name, image_version)

    async def send_pull_image_output(self, status, progress):
        # Call this method when you want to send a "pull_image_output" message
        await self.send(text_data=json.dumps({
            'status': status,
            'progress': progress
        }))

    async def pull_image_input(self, image_name, image_version):
        client = docker.APIClient()
        try:
            x = client.pull(image_name, stream=True,decode=True,tag=image_version)
        except docker.errors.APIError as err:
            print(f"[{type(err)}] {str(err)}")
            await self.send_pull_image_output(str(err), "")
            #useless sleep
            await asyncio.sleep(3)
            self.close()
            return

        for item in x:
            if "progress" not in item:
                item["progress"] = ""
            if "errorDetail" in item:
                item["status"] = item["errorDetail"]["message"]

            await self.send_pull_image_output(
                status=item["status"],
                progress=item["progress"]
            )

        await asyncio.sleep(1.5)
        await self.close()

class NotificationConsumer(AuthenticatedConsumer):
    room_group_name = 'group_notifications'

    async def connected(self):
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

    async def disconnect(self, close_code):
        if self.user is not None:
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from room group
    async def send_notification(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))


def send_notification_to_group(message):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'group_notifications',  # Must match the group name used in your consumer
        {
            'type': 'send_notification',
            'message': message
        }
    )

