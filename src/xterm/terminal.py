"""The byte streams behind the web terminals.

- ContainerShell: a shell started with `docker exec` in a running container (Console button).
- ContainerAttach: the main process of a running container (Attach button).
- HostShell: bash in this app's own container, on a local pseudo-terminal (Terminal page).

Each one gives the consumer the same five things: a file descriptor to watch for output,
read(), write(), resize() and close(). OutputDecoder turns what read() returns into text.

For the Docker streams, docker-py hands back the connection (`socket=True`) as a read-only
socket.SocketIO, and closing that leaves the connection open until the garbage collector frees
docker-py's response. So DockerStream works on its own socket object over a duplicate of the
descriptor: it can write, and its shutdown() ends the connection right away.
"""
import codecs
import fcntl
import os
import pty
import shlex
import signal
import socket
import struct
import termios
import time
import uuid
from typing import Optional

import docker

from xterm.docker_client import docker_client

# Bytes read per wake-up of the event loop.
READ_SIZE = 4096
# Longest a write to a container may block (the daemon not reading at all) before it fails.
WRITE_TIMEOUT = 10

# Where ContainerShell leaves the shell's PID inside the container, and the prefix of the file.
PID_FILE_DIR = "/tmp"
PID_FILE_PREFIX = "django-docker-gui-"

# Started with `sh -c` in the container. It writes its PID down, then becomes bash (or sh when the
# image has no bash, e.g. Alpine). Docker has no call to stop an exec'd process, and the shell keeps
# running when the connection drops, so close() needs that PID.
START_SHELL = "echo $$ > {pid_file}; if command -v bash >/dev/null 2>&1; then exec bash; else exec sh; fi"
# Interactive shells ignore SIGTERM; SIGHUP is what a closing terminal sends.
STOP_SHELL = 'kill -HUP "$(cat {pid_file})" 2>/dev/null; rm -f {pid_file}'

# How long HostShell waits for bash to exit after SIGHUP before it sends SIGKILL.
HOST_SHELL_EXIT_GRACE = 1.0


class ContainerUnavailable(Exception):
    """The container doesn't exist or isn't running."""


class OutputDecoder:
    """Turns the bytes of a session into text for xterm.js.

    UTF-8 is decoded incrementally, so a character split across two reads comes out whole.
    Without a TTY, Docker multiplexes stdout and stderr: every frame starts with an 8-byte header
    (stream type, three zero bytes, payload length as a big-endian uint32). With `multiplexed`
    set, those headers are taken out, however the frames are split across reads.
    """

    FRAME_HEADER = struct.Struct(">BxxxL")

    def __init__(self, multiplexed: bool = False):
        self.multiplexed = multiplexed
        self._pending = b""
        self._utf8 = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def feed(self, data: bytes) -> str:
        if self.multiplexed:
            data = self._payload(data)
        return self._utf8.decode(data)

    def _payload(self, data: bytes) -> bytes:
        self._pending += data
        payload = bytearray()
        header = self.FRAME_HEADER
        while len(self._pending) >= header.size:
            _, length = header.unpack_from(self._pending)
            end = header.size + length
            if len(self._pending) < end:
                break
            payload += self._pending[header.size:end]
            self._pending = self._pending[end:]
        return bytes(payload)


def write_all(write, data: bytes) -> None:
    """Call `write` until every byte is out (socket and pty writes may take only part)."""
    view = memoryview(data)
    while view:
        view = view[write(view):]


def running_container(api, container_id: str) -> dict:
    """`docker inspect` of a running container; ContainerUnavailable otherwise."""
    try:
        info = api.inspect_container(container_id)
    except docker.errors.NotFound as exc:
        raise ContainerUnavailable(f"No such container: {container_id}") from exc
    if not info["State"]["Running"]:
        raise ContainerUnavailable(f"Container {info['Name'].lstrip('/')} is not running")
    return info


class DockerStream:
    """What the two container sessions share: the connection docker-py opened, and its client."""

    multiplexed = False
    sock = None

    def __init__(self, client: docker.DockerClient):
        self.client = client
        self.api = client.api

    @classmethod
    def open(cls, container_id: str):
        """A session on its own Docker client, which close() closes again."""
        client = docker_client()
        try:
            return cls(client, container_id)
        except BaseException:
            client.close()
            raise

    def adopt(self, docker_socket) -> None:
        """Take over the connection docker-py returned (see the module docstring)."""
        self._docker_socket = docker_socket  # keeps docker-py's response alive until close()
        self.sock = socket.socket(fileno=os.dup(docker_socket.fileno()))
        self.sock.settimeout(WRITE_TIMEOUT)

    def fileno(self) -> int:
        return self.sock.fileno()

    def read(self) -> Optional[bytes]:
        try:
            return self.sock.recv(READ_SIZE, socket.MSG_DONTWAIT)
        except BlockingIOError:
            return None

    def write(self, data: bytes) -> None:
        self.sock.sendall(data)

    def resize(self, rows: int, cols: int, width: int = 0, height: int = 0) -> None:
        """Most sessions can't be resized; the ones that can override this."""

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # the other side hung up first
            self.sock.close()
            self._docker_socket.close()
            self.sock = None
        self.client.close()


class ContainerShell(DockerStream):
    def __init__(self, client: docker.DockerClient, container_id: str):
        super().__init__(client)
        self.container_id = container_id
        running_container(self.api, container_id)
        self.pid_file = shlex.quote(f"{PID_FILE_DIR}/{PID_FILE_PREFIX}{uuid.uuid4().hex}.pid")
        self.exec_id = self.api.exec_create(
            container_id, ["sh", "-c", START_SHELL.format(pid_file=self.pid_file)],
            stdin=True, tty=True, stdout=True, stderr=True,
        )["Id"]
        # tty=True here too, or Docker multiplexes the stream even though the exec has a TTY.
        self.adopt(self.api.exec_start(self.exec_id, tty=True, socket=True))

    def resize(self, rows: int, cols: int, width: int = 0, height: int = 0) -> None:
        self.api.exec_resize(self.exec_id, height=rows, width=cols)

    def close(self) -> None:
        try:
            stop = self.api.exec_create(self.container_id, ["sh", "-c", STOP_SHELL.format(pid_file=self.pid_file)])
            self.api.exec_start(stop["Id"])
        except docker.errors.APIError:
            pass  # the container stopped or went away, and the shell with it
        finally:
            super().close()


class ContainerAttach(DockerStream):
    """Resizing is ignored on purpose: the TTY belongs to the container's main process and is
    shared by everyone attached to it."""

    def __init__(self, client: docker.DockerClient, container_id: str):
        super().__init__(client)
        info = running_container(self.api, container_id)
        self.multiplexed = not info["Config"]["Tty"]
        self.adopt(self.api.attach_socket(
            container_id, params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
        ))


class HostShell:
    multiplexed = False

    def __init__(self, shell: str = "bash"):
        pid, fd = pty.fork()
        if pid == 0:  # the child: become the shell, never return into the server code
            try:
                os.environ["TERM"] = "xterm"
                os.execlp(shell, shell)
            finally:
                os._exit(127)
        self.pid, self.fd = pid, fd

    def fileno(self) -> int:
        return self.fd

    def read(self) -> bytes:
        try:
            return os.read(self.fd, READ_SIZE)
        except OSError:  # EIO once the shell has exited and the pty is gone
            return b""

    def write(self, data: bytes) -> None:
        write_all(lambda chunk: os.write(self.fd, chunk), data)

    def resize(self, rows: int, cols: int, width: int = 0, height: int = 0) -> None:
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, width, height))

    def close(self) -> None:
        if self.pid is None:
            return
        pid, self.pid = self.pid, None
        try:
            os.kill(pid, signal.SIGHUP)
            if not self._reaped(pid, HOST_SHELL_EXIT_GRACE):
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
        except (ProcessLookupError, ChildProcessError):
            pass  # already gone
        finally:
            os.close(self.fd)

    @staticmethod
    def _reaped(pid: int, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if os.waitpid(pid, os.WNOHANG) != (0, 0):
                return True
            time.sleep(0.05)
        return False
