import asyncio
import json
import os
from unittest import mock

from django.test import SimpleTestCase

from xterm import terminal
from xterm.terminal import OutputDecoder
from xterm.tests.fakes import FakeApi, FakeClient, multiplexed_frame
from xterm.tests.helpers import ConsumerTestCase, communicator

TEXT = "héllo 你好 ╔═╗\r\n"


class OutputDecoderTests(SimpleTestCase):
    def test_utf8_split_anywhere_comes_out_whole(self):
        data = TEXT.encode()
        for cut in range(1, len(data)):
            with self.subTest(cut=cut):
                decoder = OutputDecoder()
                self.assertEqual(decoder.feed(data[:cut]) + decoder.feed(data[cut:]), TEXT)

    def test_nothing_is_dropped_from_long_output(self):
        # The old reader cut 8 characters off every 1024-byte read.
        data = " ".join(str(n) for n in range(1, 2000)).encode()
        decoder = OutputDecoder()
        chunks = [data[i:i + 1024] for i in range(0, len(data), 1024)]
        self.assertEqual("".join(decoder.feed(c) for c in chunks), data.decode())

    def test_invalid_bytes_are_replaced_not_fatal(self):
        self.assertEqual(OutputDecoder().feed(b"ok\xff!"), "ok�!")

    def test_multiplexed_frames_are_unwrapped_however_they_are_split(self):
        stream = multiplexed_frame(1, "out 你好\n".encode()) + multiplexed_frame(2, b"err\n") + multiplexed_frame(1, b"")
        for cut in range(len(stream) + 1):
            for second_cut in (cut, min(cut + 3, len(stream))):
                with self.subTest(cut=cut, second_cut=second_cut):
                    decoder = OutputDecoder(multiplexed=True)
                    parts = [stream[:cut], stream[cut:second_cut], stream[second_cut:]]
                    self.assertEqual("".join(decoder.feed(p) for p in parts), "out 你好\nerr\n")


def fake_docker(**containers):
    client = FakeClient(FakeApi(containers))
    return client, mock.patch("xterm.terminal.docker_client", return_value=client)


class ConsoleTests(ConsumerTestCase):
    async def open_console(self, action, container_id="abc"):
        ws = communicator("/ws/console/", self.protocols(self.member, f"container.{container_id}"))
        connected, subprotocol = await ws.connect()
        self.assertTrue(connected)
        self.assertEqual(subprotocol, f"container.{container_id}")
        await ws.send_to(text_data=json.dumps({"action": action, "payload": {"Id": container_id}}))
        return ws

    async def remote(self, api, index=0):
        for _ in range(100):
            if len(api.remote_ends) > index:
                return api.remote_ends[index]
            await asyncio.sleep(0.01)
        self.fail("no stream was opened")

    async def receive_text(self, ws, expected):
        text = ""
        while len(text) < len(expected):
            text += await ws.receive_from(timeout=3)
        return text

    async def test_shell_runs_bash_or_sh_with_a_tty_and_streams_text(self):
        client, patched = fake_docker(abc={"running": True})
        with patched:
            ws = await self.open_console("shell")
            remote = await self.remote(client.api)
            data = TEXT.encode()
            remote.sendall(data[:2])  # "h" and half of "é"
            await asyncio.sleep(0.05)
            remote.sendall(data[2:])
            self.assertEqual(await self.receive_text(ws, TEXT), TEXT)

            _, container_id, cmd, kwargs = client.api.calls_named("exec_create")[0]
            self.assertEqual(container_id, "abc")
            self.assertEqual(cmd[:2], ["sh", "-c"])
            self.assertIn("exec bash; else exec sh", cmd[2])
            self.assertTrue(kwargs["tty"] and kwargs["stdin"])
            self.assertEqual(client.api.calls_named("exec_start")[0][2], {"tty": True, "socket": True})
            await ws.disconnect()

    async def test_keys_and_resizes_reach_the_shell(self):
        client, patched = fake_docker(abc={"running": True})
        with patched:
            ws = await self.open_console("shell")
            remote = await self.remote(client.api)
            await ws.send_to(text_data=json.dumps({"action": "pty_input", "payload": {"input": "ls 你好\r"}}))
            self.assertEqual(await asyncio.to_thread(remote.recv, 100), "ls 你好\r".encode())
            for size in ({"rows": 40, "cols": 120, "width": 900, "height": 700}, {"rows": 0, "cols": 80},
                         {"rows": "x", "cols": 80}, None):
                await ws.send_to(text_data=json.dumps({"action": "pty_resize", "payload": {"size": size}}))
            await ws.send_to(text_data="not json")
            await ws.send_to(text_data=json.dumps({"action": "pty_input", "payload": {"input": "!"}}))
            self.assertEqual(await asyncio.to_thread(remote.recv, 10), b"!")  # still alive after the junk
            self.assertEqual(client.api.calls_named("exec_resize"), [("exec_resize", "exec-1", 40, 120)])
            await ws.disconnect()

    async def test_closing_the_page_ends_the_shell_and_the_connection(self):
        client, patched = fake_docker(abc={"running": True})
        with patched:
            ws = await self.open_console("shell")
            remote = await self.remote(client.api)
            await ws.disconnect()
            stop = client.api.calls_named("exec_create")[1]
            start_cmd = client.api.calls_named("exec_create")[0][2][2]
            pid_file = start_cmd.split("echo $$ > ")[1].split(";")[0]
            self.assertEqual(stop[2], ["sh", "-c", f'kill -HUP "$(cat {pid_file})" 2>/dev/null; rm -f {pid_file}'])
            self.assertEqual(client.api.calls_named("exec_start")[1][1], "exec-2")
            self.assertEqual(await asyncio.to_thread(remote.recv, 10), b"")  # the stream was hung up, not left to the GC
            self.assertTrue(client.closed)

    async def test_shell_exit_closes_the_page(self):
        client, patched = fake_docker(abc={"running": True})
        with patched:
            ws = await self.open_console("shell")
            remote = await self.remote(client.api)
            remote.sendall(b"bye\r\n")
            remote.close()
            self.assertEqual(await ws.receive_from(timeout=3), "bye\r\n")
            self.assertEqual((await ws.receive_output(timeout=3))["type"], "websocket.close")
            await ws.disconnect()

    async def test_attach_unwraps_non_tty_output_and_ignores_resize(self):
        client, patched = fake_docker(abc={"running": True, "tty": False})
        with patched:
            ws = await self.open_console("attach")
            remote = await self.remote(client.api)
            remote.sendall(multiplexed_frame(1, "tick 你好\n".encode()) + multiplexed_frame(2, b"oops\n"))
            self.assertEqual(await self.receive_text(ws, "tick 你好\noops\n"), "tick 你好\noops\n")
            await ws.send_to(text_data=json.dumps({"action": "pty_resize", "payload": {"size": {"rows": 5, "cols": 5}}}))
            await ws.disconnect()
            self.assertEqual(client.api.calls_named("exec_resize"), [])
            self.assertEqual(client.api.calls_named("exec_create"), [])  # attach never kills anything
            self.assertEqual(await asyncio.to_thread(remote.recv, 10), b"")

    async def test_attach_to_a_tty_container_passes_bytes_through(self):
        client, patched = fake_docker(abc={"running": True, "tty": True})
        with patched:
            ws = await self.open_console("attach")
            remote = await self.remote(client.api)
            remote.sendall(TEXT.encode())
            self.assertEqual(await self.receive_text(ws, TEXT), TEXT)
            await ws.disconnect()

    async def test_stopped_or_missing_containers_close_with_4004(self):
        for container_id in ("stopped", "missing"):
            for action in ("shell", "attach"):
                with self.subTest(container=container_id, action=action):
                    client, patched = fake_docker(stopped={"running": False})
                    with patched, self.assertLogs("xterm.consumers", "INFO"):
                        ws = await self.open_console(action, container_id)
                        closed = await ws.receive_output(timeout=3)
                        self.assertEqual(closed, {"type": "websocket.close", "code": 4004})
                        self.assertTrue(client.closed)
                        await ws.disconnect()

    async def test_unknown_first_message_starts_nothing(self):
        client, patched = fake_docker(abc={"running": True})
        with patched:
            ws = await self.open_console("format-disk")
            await ws.send_to(text_data=json.dumps({"action": "shell", "payload": {"Id": 42}}))
            await asyncio.sleep(0.1)
            self.assertEqual(client.api.calls, [])
            await ws.disconnect()


class HostTerminalTests(ConsumerTestCase):
    async def test_superuser_gets_a_working_shell_that_ends_with_the_page(self):
        started = []
        real_host_shell = terminal.HostShell

        def spy():
            shell = real_host_shell()
            started.append(shell.pid)
            return shell

        with mock.patch("xterm.consumers.HostShell", spy):
            ws = communicator("/ws/terminal/", self.protocols(self.admin, "terminal.abc"))
            connected, subprotocol = await ws.connect()
            self.assertTrue(connected)
            self.assertEqual(subprotocol, "terminal.abc")
            await ws.send_to(text_data=json.dumps({"action": "pty_resize", "payload": {"size": {"rows": 30, "cols": 100}}}))
            await ws.send_to(text_data=json.dumps({"action": "pty_input", "payload": {"input": "echo $((6*7)) $(stty size)\n"}}))
            output = ""
            while "42 30 100" not in output:
                output += await ws.receive_from(timeout=5)
            await ws.disconnect()
        with self.assertRaises(ChildProcessError):  # reaped, not left as a zombie
            os.waitpid(started[0], os.WNOHANG)

    async def test_typing_exit_closes_the_page(self):
        ws = communicator("/ws/terminal/", self.protocols(self.admin, "terminal.abc"))
        self.assertTrue((await ws.connect())[0])
        await ws.send_to(text_data=json.dumps({"action": "pty_input", "payload": {"input": "exit\n"}}))
        while (message := await ws.receive_output(timeout=5))["type"] != "websocket.close":
            pass
        await ws.disconnect()
