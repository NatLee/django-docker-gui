import docker
from django_rq import job


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
    msg = f"Container {container_name} ({image_name}) has been created"
    return msg

@job
def remove_image_task(image_id):
    client = docker.from_env()
    try:
        client.images.remove(image=image_id)
        msg = f"Image {image_id} has been removed"
    except docker.errors.APIError as err:
        msg = str(err)
    return msg

@job
def run_container_task(id):
    client = docker.from_env()
    container = client.containers.get(id)
    container.start()
    container_name = container.name
    msg = f"Container {container_name} has been started"
    return msg

@job
def stop_container_task(id):
    client = docker.from_env()
    container = client.containers.get(id)
    container.stop()
    container_name = container.name
    msg = f"Container {container_name} has been stopped"
    return msg

@job
def remove_container_task(id):
    client = docker.from_env()
    container = client.containers.get(id)
    container.remove()
    container_name = container.name
    msg = f"Container {container_name} has been removed"
    return msg

@job
def restart_container_task(id):
    client = docker.from_env()
    container = client.containers.get(id)
    container.restart()
    container_name = container.name
    msg = f"Container {container_name} has been restarted"
    return msg
