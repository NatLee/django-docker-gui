"""The one place that builds Docker clients.

docker.from_env() honours DOCKER_HOST and the other DOCKER_* variables and falls back to
/var/run/docker.sock, so every view, job and consumer talks to the same daemon (the old code
mixed from_env() with APIClient(), which always used the default socket). Tests replace this.
"""
import docker


def docker_client() -> docker.DockerClient:
    return docker.from_env()
