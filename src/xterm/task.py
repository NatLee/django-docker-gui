"""Background jobs, run by `manage.py rqworker`. Each does one Docker call and then tells every
open page what happened (xterm/notifications.py), also when it fails."""
from contextlib import closing

import docker
from django_rq import job

from xterm.docker_client import docker_client
from xterm.notifications import notify

# What the Containers page can ask for, and the event announced when it's done.
CONTAINER_ACTIONS = {"start": "STARTED", "stop": "STOPPED", "restart": "RESTARTED", "remove": "REMOVED"}


def reason(exc: docker.errors.APIError) -> str:
    """The daemon's own words ("container is running: stop the container before removing...")."""
    return exc.explanation or str(exc)


def fail(what: str, exc: docker.errors.APIError):
    notify("FAILED", f"Could not {what}: {reason(exc)}")
    raise exc  # RQ keeps the job in its failed registry (see the RQ page in the admin)


@job
def container_action_task(container_id: str, action: str) -> str:
    event = CONTAINER_ACTIONS[action]
    with closing(docker_client()) as client:
        try:
            container = client.containers.get(container_id)
            getattr(container, action)()
        except docker.errors.APIError as exc:
            fail(f"{action} container [{container_id[:12]}]", exc)
    msg = f"Container [{container.name}] has been {event.lower()}"
    notify(event, msg)
    return msg


@job
def run_image_task(image_id: str) -> str:
    with closing(docker_client()) as client:
        try:
            container = client.containers.run(image_id, stdin_open=True, detach=True, tty=True)
        except docker.errors.APIError as exc:
            fail(f"run image [{image_id}]", exc)
        image_name = container.image.tags[0] if container.image.tags else "none"
    msg = f"Container [{container.name}] ({image_name}) has been created"
    notify("CREATED", msg)
    return msg


@job
def remove_image_task(image_id: str) -> str:
    with closing(docker_client()) as client:
        try:
            client.images.remove(image=image_id)
        except docker.errors.APIError as exc:
            fail(f"remove image [{image_id}]", exc)
    msg = f"Image [{image_id}] has been removed"
    notify("REMOVED", msg)
    return msg
