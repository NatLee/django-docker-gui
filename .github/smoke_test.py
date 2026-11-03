"""Smoke test against the running stack, the way a browser uses it: log in over HTTP, then the
notifications and console WebSockets through Daphne. Used by CI after `docker compose up`.

usage: python smoke_test.py <base url> <username> <password> <id of a running container with a shell>
"""
import asyncio
import base64
import json
import sys

import requests
import websockets

BASE, USERNAME, PASSWORD, CONTAINER = sys.argv[1:5]
WS = BASE.replace("http", "ws", 1)


def check(what, ok):
    print(("ok   " if ok else "FAIL ") + what, flush=True)
    if not ok:
        sys.exit(1)


def token_protocol(token):
    return "token." + base64.b64encode(token.encode()).decode().rstrip("=")


async def refused(path, protocols):
    try:
        async with websockets.connect(WS + path, subprotocols=protocols, open_timeout=10):
            return False
    except websockets.InvalidStatus as exc:
        return exc.response.status_code == 403


async def main():
    for page in ("/login", "/containers", "/terminal", "/api/__hidden_statics/js/terminal-session.js"):
        check(f"GET {page} is 200", requests.get(BASE + page, timeout=10).status_code == 200)
    bad = requests.post(f"{BASE}/api/auth/token", json={"username": USERNAME, "password": "wrong"}, timeout=10)
    check("wrong password is 401", bad.status_code == 401)
    token = requests.post(f"{BASE}/api/auth/token", json={"username": USERNAME, "password": PASSWORD},
                          timeout=10).json()["access_token"]
    containers = requests.get(f"{BASE}/api/containers", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    check("container list with the token", containers.status_code == 200 and CONTAINER in containers.text)
    check("container list without a token is 401", requests.get(f"{BASE}/api/containers", timeout=10).status_code == 401)

    check("notifications socket refuses a missing token", await refused("/ws/notifications/", ["notifications"]))
    async with websockets.connect(WS + "/ws/notifications/", subprotocols=["notifications", token_protocol(token)]) as ws:
        check("notifications socket accepts the token", ws.subprotocol == "notifications")

    async with websockets.connect(WS + "/ws/console/", subprotocols=[f"container.{CONTAINER}", token_protocol(token)]) as ws:
        await ws.send(json.dumps({"action": "shell", "payload": {"Id": CONTAINER}}))
        # printf turns the octal escapes into the UTF-8 bytes of 你好, whatever the container's locale.
        keys = r"printf '\344\275\240\345\245\275 %s\n' $((6*7))" + "\r"
        await ws.send(json.dumps({"action": "pty_input", "payload": {"input": keys}}))
        output = ""
        try:
            while "你好 42" not in output:
                output += await asyncio.wait_for(ws.recv(), timeout=15)
        except asyncio.TimeoutError:
            pass
        check("console runs a command and shows UTF-8 output", "你好 42" in output)


asyncio.run(main())
