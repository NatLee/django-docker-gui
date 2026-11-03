from datetime import timedelta

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.test import SimpleTestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from xterm import notifications
from xterm.ws_auth import decode_token, read_subprotocols
from xterm.tests.helpers import ConsumerTestCase, access_token, communicator, token_protocol

# Every WebSocket route of the app. The console and terminal start a shell only after a message,
# so connecting alone is safe here.
ALL_PATHS = ["/ws/console/", "/ws/terminal/", "/ws/pull-image/", "/ws/notifications/"]


class SubprotocolParsingTests(SimpleTestCase):
    def test_token_with_and_without_padding(self):
        for raw in ["a", "ab", "abc", "header.payload.signature"]:
            for padded in (True, False):
                with self.subTest(raw=raw, padded=padded):
                    value = token_protocol(raw, padded=padded)[len("token."):]
                    self.assertEqual(decode_token(value), raw)

    def test_garbled_token_is_none(self):
        self.assertIsNone(decode_token("not base64!"))
        self.assertIsNone(decode_token("/w"))  # decodes to a non-ASCII byte

    def test_accepts_with_the_first_name_not_the_token(self):
        offered = read_subprotocols([token_protocol("jwt"), "container.abc", "other"])
        self.assertEqual(offered.token, "jwt")
        self.assertEqual(offered.accept_with, "container.abc")

    def test_nothing_offered(self):
        offered = read_subprotocols(None)
        self.assertIsNone(offered.token)
        self.assertIsNone(offered.accept_with)


class WebSocketLoginTests(ConsumerTestCase):
    async def assert_refused(self, path, protocols):
        ws = communicator(path, protocols)
        with self.assertLogs("xterm.consumers", "WARNING") as logs:
            connected, _ = await ws.connect()
        self.assertFalse(connected, f"{path} accepted {protocols!r}")
        self.assertIn("refused", logs.output[0])
        await ws.disconnect()

    async def test_every_socket_refuses_without_a_token(self):
        for path in ALL_PATHS:
            with self.subTest(path=path):
                await self.assert_refused(path, [])
                await self.assert_refused(path, ["notifications"])

    async def test_every_socket_refuses_bad_tokens(self):
        expired = AccessToken.for_user(self.admin)
        expired.set_exp(lifetime=-timedelta(seconds=1))
        refresh = RefreshToken.for_user(self.admin)  # right signature, wrong token type
        bad = [token_protocol("garbage"), token_protocol(str(expired)), token_protocol(str(refresh)),
               "token.%%%"]
        for path in ALL_PATHS:
            for protocol in bad:
                with self.subTest(path=path, protocol=protocol[:20]):
                    await self.assert_refused(path, ["name", protocol])

    async def test_inactive_or_deleted_users_are_refused(self):
        token = access_token(self.admin)
        await sync_to_async(User.objects.filter(pk=self.admin.pk).update)(is_active=False)
        await self.assert_refused("/ws/notifications/", ["n", token_protocol(token)])
        await sync_to_async(User.objects.filter(pk=self.admin.pk).delete)()
        await self.assert_refused("/ws/notifications/", ["n", token_protocol(token)])

    async def test_accepts_padded_and_unpadded_tokens_and_answers_with_the_name(self):
        for padded in (False, True):
            with self.subTest(padded=padded):
                ws = communicator("/ws/notifications/", ["notifications", token_protocol(access_token(self.member), padded)])
                connected, subprotocol = await ws.connect()
                self.assertTrue(connected)
                self.assertEqual(subprotocol, "notifications")
                await ws.disconnect()

    async def test_host_terminal_is_for_superusers_only(self):
        await self.assert_refused("/ws/terminal/", self.protocols(self.member, "terminal.x"))

    async def test_console_and_pull_are_for_any_active_account(self):
        for path in ("/ws/console/", "/ws/pull-image/"):
            with self.subTest(path=path):
                ws = communicator(path, self.protocols(self.member, "container.x"))
                connected, _ = await ws.connect()
                self.assertTrue(connected)
                await ws.disconnect()

    async def test_notifications_reach_logged_in_listeners(self):
        ws = communicator("/ws/notifications/", self.protocols(self.member, "notifications"))
        self.assertTrue((await ws.connect())[0])
        await get_channel_layer().group_send(
            notifications.GROUP, {"type": "send_notification", "message": {"action": "STARTED"}}
        )
        self.assertEqual(await ws.receive_json_from(), {"message": {"action": "STARTED"}})
        await ws.disconnect()
