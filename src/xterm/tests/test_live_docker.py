"""The console against a real Docker daemon. Skipped unless DOCKER_LIVE_TESTS=1.

CI runs these inside the started app container (it has the Docker socket). They create their
own containers, named django-docker-gui-live-<random>, and remove them again.
"""
import asyncio
import json
import os
import unittest
import uuid

import docker

from xterm.tests.helpers import ConsumerTestCase, communicator

LIVE = os.environ.get("DOCKER_LIVE_TESTS") == "1"
# An image with bash and one without (the console falls back to sh there).
IMAGE_WITH_BASH = os.environ.get("LIVE_TEST_IMAGE", "debian:trixie-slim")
IMAGE_WITHOUT_BASH = os.environ.get("LIVE_TEST_IMAGE_NO_BASH", "alpine:3.22")
# Lists the shells still running in a container, one "pid name" per line.
LIST_SHELLS = ["sh", "-c", 'for p in /proc/[0-9]*; do n=$(cat $p/comm 2>/dev/null); '
                           'case "$n" in bash|sh) echo "${p#/proc/} $n";; esac; done']


@unittest.skipUnless(LIVE, "set DOCKER_LIVE_TESTS=1 to run against a real Docker daemon")
class LiveConsoleTests(ConsumerTestCase):
    def setUp(self):
        super().setUp()
        self.docker = docker.from_env()
        self.created = []

    def tearDown(self):
        for container in self.created:
            container.remove(force=True)
        self.docker.close()

    def start(self, image, command, tty):
        try:
            self.docker.images.get(image)
        except docker.errors.ImageNotFound:
            self.docker.images.pull(image)
        container = self.docker.containers.run(
            image, command, name=f"django-docker-gui-live-{uuid.uuid4().hex[:8]}",
            detach=True, tty=tty, stdin_open=tty,
        )
        self.created.append(container)
        return container

    def shells(self, container):
        """Shells running in the container, apart from PID 1 and the one doing the listing."""
        out = container.exec_run(LIST_SHELLS).output.decode().split("\n")
        return sorted(line for line in out if line and not line.startswith("1 ") and " sh" not in line)

    async def console(self, action, container):
        ws = communicator("/ws/console/", self.protocols(self.member, f"container.{container.id}"))
        self.assertTrue((await ws.connect())[0])
        await ws.send_to(text_data=json.dumps({"action": action, "payload": {"Id": container.id}}))
        return ws

    async def read_until(self, ws, marker, seconds=10):
        text = ""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + seconds
        while marker not in text:
            text += await ws.receive_from(timeout=max(deadline - loop.time(), 0.1))
        return text

    async def type(self, ws, keys):
        await ws.send_to(text_data=json.dumps({"action": "pty_input", "payload": {"input": keys}}))

    async def test_shell_output_is_complete_and_the_shell_ends_with_the_page(self):
        container = await asyncio.to_thread(self.start, IMAGE_WITH_BASH, "bash", True)
        ws = await self.console("shell", container)
        await self.type(ws, "printf '\\344\\275\\240\\345\\245\\275 %s\\n' $((6*7)); seq 1 3000 | tr '\\n' ' '; echo END\r")
        text = await self.read_until(ws, "2999 3000 END")
        self.assertIn("你好 42", text)
        self.assertIn(" ".join(str(n) for n in range(1, 3001)) + " END", text.replace("\r\n", ""))
        self.assertEqual(len(await asyncio.to_thread(self.shells, container)), 1, "the console's bash")
        await ws.disconnect()
        for _ in range(50):
            if not await asyncio.to_thread(self.shells, container):
                break
            await asyncio.sleep(0.1)
        self.assertEqual(await asyncio.to_thread(self.shells, container), [])
        leftovers = (await asyncio.to_thread(container.exec_run, ["sh", "-c", "ls /tmp"])).output.decode()
        self.assertNotIn("django-docker-gui-", leftovers)

    async def test_shell_falls_back_to_sh_without_bash(self):
        container = await asyncio.to_thread(self.start, IMAGE_WITHOUT_BASH, "sleep 1d", False)
        ws = await self.console("shell", container)
        await self.type(ws, "echo shell=$((40+2))\r")
        self.assertIn("shell=42", await self.read_until(ws, "shell=42"))
        await ws.disconnect()

    async def test_attach_to_a_container_without_tty(self):
        container = await asyncio.to_thread(
            self.start, IMAGE_WITHOUT_BASH, ["sh", "-c", "while true; do echo tick 你好; sleep 0.2; done"], False
        )
        ws = await self.console("attach", container)
        text = await self.read_until(ws, "tick 你好\ntick 你好")
        self.assertNotIn("\x01\x00\x00\x00", text)  # no stream headers in the output
        await ws.disconnect()
        await asyncio.to_thread(container.reload)
        self.assertEqual(container.status, "running")  # detaching leaves the container alone
