import json
import threading
from unittest import mock

import docker
from channels.layers import get_channel_layer

from xterm import notifications
from xterm.tests.fakes import FakeClient
from xterm.tests.helpers import ConsumerTestCase, communicator


class PullTests(ConsumerTestCase):
    def patched_pull(self, pull):
        client = FakeClient()
        client.api.pull = pull
        return client, mock.patch("xterm.consumers.docker_client", return_value=client)

    async def pull(self, payload):
        ws = communicator("/ws/pull-image/", self.protocols(self.member, "pull-image"))
        self.assertTrue((await ws.connect())[0])
        await ws.send_to(text_data=json.dumps({"action": "pull_image", "payload": payload}))
        messages = []
        while (out := await ws.receive_output(timeout=3))["type"] == "websocket.send":
            messages.append(json.loads(out["text"]))
        await ws.disconnect()
        return messages

    async def test_streams_progress_then_closes(self):
        calls = []

        def pull(image, tag, stream, decode):
            calls.append((image, tag, stream, decode))
            yield {"status": "Pulling from library/alpine", "id": "3.22"}
            yield {"status": "Downloading", "progress": "[==>   ] 1MB/4MB", "id": "abc"}
            yield {"errorDetail": {"message": "toomanyrequests"}, "error": "toomanyrequests"}

        client, patched = self.patched_pull(pull)
        with patched:
            messages = await self.pull({"image": " alpine ", "version": "3.22"})
        self.assertEqual(calls, [("alpine", "3.22", True, True)])
        self.assertEqual(messages, [
            {"status": "Pulling from library/alpine", "progress": ""},
            {"status": "Downloading", "progress": "[==>   ] 1MB/4MB"},
            {"status": "toomanyrequests", "progress": ""},
        ])
        self.assertTrue(client.closed)

    async def test_empty_version_means_latest(self):
        # It used to default to "lastest".
        tags = []

        def pull(image, tag, **kwargs):
            tags.append(tag)
            return iter([])

        _, patched = self.patched_pull(pull)
        with patched:
            await self.pull({"image": "alpine"})
            await self.pull({"image": "alpine", "version": "  "})
        self.assertEqual(tags, ["latest", "latest"])

    async def test_daemon_errors_are_shown_not_raised(self):
        def pull(image, tag, **kwargs):
            raise docker.errors.NotFound("manifest for alpine:nope not found")

        _, patched = self.patched_pull(pull)
        with patched, self.assertLogs("xterm.consumers", "INFO"):
            messages = await self.pull({"image": "alpine", "version": "nope"})
        self.assertEqual(len(messages), 1)
        self.assertIn("manifest for alpine:nope not found", messages[0]["status"])

    async def test_other_sockets_keep_working_during_a_pull(self):
        release = threading.Event()

        def pull(image, tag, **kwargs):
            release.wait(5)  # the daemon takes its time
            yield {"status": "done"}

        listener = communicator("/ws/notifications/", self.protocols(self.member, "notifications"))
        self.assertTrue((await listener.connect())[0])
        _, patched = self.patched_pull(pull)
        with patched:
            ws = communicator("/ws/pull-image/", self.protocols(self.member, "pull-image"))
            self.assertTrue((await ws.connect())[0])
            await ws.send_to(text_data=json.dumps({"action": "pull_image", "payload": {"image": "big"}}))
            await get_channel_layer().group_send(notifications.GROUP, {"type": "send_notification", "message": "hi"})
            self.assertEqual(await listener.receive_json_from(timeout=2), {"message": "hi"})
            release.set()
            self.assertEqual(json.loads(await ws.receive_from(timeout=3)), {"status": "done", "progress": ""})
            await ws.disconnect()
        await listener.disconnect()

    async def test_ignores_messages_without_an_image(self):
        pull = mock.Mock()
        _, patched = self.patched_pull(pull)
        with patched:
            ws = communicator("/ws/pull-image/", self.protocols(self.member, "pull-image"))
            self.assertTrue((await ws.connect())[0])
            for message in ['{"action": "pull_image", "payload": {"image": ""}}', '{"action": "rm -rf"}', "[]", "x"]:
                await ws.send_to(text_data=message)
            self.assertTrue(await ws.receive_nothing(timeout=0.3))
            await ws.disconnect()
        pull.assert_not_called()
