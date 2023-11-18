import docker
from django_rq import job
from xterm.consumers import send_notification_to_group

@job
def run_image_task(image_id):
    client = docker.from_env()
    container = client.containers.run(
        image_id,
        stdin_open=True,
        detach=True,
        tty=True,
    )
    image_name = "none"
    if container.image.tags:
        image_name = container.image.tags[0]

    container_name = container.attrs['Name'][1:]

    msg = f"Container [{container_name}] ({image_name}) has been created"

    message = {
        "action": "CREATED",
        "details": msg
    }
    send_notification_to_group(message=message)
    return msg

@job
def remove_image_task(image_id):
    client = docker.from_env()

    client.images.remove(image=image_id)
    msg = f"Image [{image_id}] has been removed"
    message = {
        "action": "REMOVED",
        "details": msg
    }
    send_notification_to_group(message=message)
    return msg

@job
def run_container_task(id):
    client = docker.from_env()
    container = client.containers.get(id)
    container.start()
    container_name = container.name
    msg = f"Container [{container_name}] has been started"

    message = {
        "action": "STARTED",
        "details": msg
    }
    send_notification_to_group(message=message)

    return msg

@job
def stop_container_task(id):
    client = docker.from_env()
    container = client.containers.get(id)
    container.stop()
    container_name = container.name
    msg = f"Container [{container_name}] has been stopped"
    message = {
        "action": "STOPPED",
        "details": msg
    }
    send_notification_to_group(message=message)
    return msg

@job
def remove_container_task(id):
    client = docker.from_env()
    container = client.containers.get(id)
    container.remove()
    container_name = container.name
    msg = f"Container [{container_name}] has been removed"

    message = {
        "action": "REMOVED",
        "details": msg
    }
    send_notification_to_group(message=message)
    return msg

@job
def restart_container_task(id):
    client = docker.from_env()
    container = client.containers.get(id)
    container.restart()
    container_name = container.name
    msg = f"Container [{container_name}] has been restarted"

    message = {
        "action": "RESTARTED",
        "details": msg
    }
    send_notification_to_group(message=message)
    return msg
