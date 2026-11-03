"""A stand-in for the bits of docker-py the app uses, backed by real sockets for the streams."""
import socket
import struct
from types import SimpleNamespace

import docker


def multiplexed_frame(stream: int, payload: bytes) -> bytes:
    """One frame of Docker's stdout/stderr stream format (used when there's no TTY)."""
    return struct.pack(">BxxxL", stream, len(payload)) + payload


class FakeApi:
    def __init__(self, containers=None):
        # id -> {"running": bool, "tty": bool, "name": str}
        self.containers = containers or {}
        self.calls = []
        self.remote_ends = []  # the "daemon" side of every stream handed out
        self._held = []  # like docker-py, keep our side referenced, so closing the SocketIO alone
                         # does not end the connection
        self.exec_count = 0

    def _stream(self):
        ours, theirs = socket.socketpair()
        theirs.settimeout(5)
        self.remote_ends.append(theirs)
        self._held.append(ours)
        return ours.makefile("rb", buffering=0)  # a read-only socket.SocketIO, like docker-py returns

    def _container(self, container_id):
        if container_id not in self.containers:
            raise docker.errors.NotFound(f"No such container: {container_id}")
        return self.containers[container_id]

    def inspect_container(self, container_id):
        c = self._container(container_id)
        return {"Name": "/" + c.get("name", container_id), "State": {"Running": c["running"]},
                "Config": {"Tty": c.get("tty", True)}}

    def exec_create(self, container_id, cmd, **kwargs):
        self._container(container_id)
        self.exec_count += 1
        exec_id = f"exec-{self.exec_count}"
        self.calls.append(("exec_create", container_id, cmd, kwargs))
        return {"Id": exec_id}

    def exec_start(self, exec_id, **kwargs):
        self.calls.append(("exec_start", exec_id, kwargs))
        return self._stream() if kwargs.get("socket") else b""

    def exec_resize(self, exec_id, height=None, width=None):
        self.calls.append(("exec_resize", exec_id, height, width))

    def attach_socket(self, container_id, params=None):
        self._container(container_id)
        self.calls.append(("attach_socket", container_id, params))
        return self._stream()

    def calls_named(self, name):
        return [c for c in self.calls if c[0] == name]


class FakeClient:
    """docker.DockerClient with `.api` and the few high-level calls the views and jobs use."""

    def __init__(self, api=None):
        self.api = api or FakeApi()
        self.closed = False
        self.containers = SimpleNamespace()
        self.images = SimpleNamespace()

    def close(self):
        self.closed = True
