"""Pages and the JSON API behind them. Pages are plain templates; their scripts check the login
and call the API with the access token. Every API view needs CanManageDocker."""
from contextlib import closing

import docker
from django.shortcuts import redirect, render
from django.views import View
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from xterm.docker_client import docker_client
from xterm.notifications import notify
from xterm.permissions import CanManageDocker
from xterm.task import CONTAINER_ACTIONS, container_action_task, remove_image_task, run_image_task


class Index(View):
    def get(self, request):
        return redirect('/login')


class Page(View):
    """A page of the app: the template does the rest in the browser."""

    template_name = None

    def get(self, request, **kwargs):
        return render(request, self.template_name)


# Results shown on the Docker Hub page (the daemon returns at most 100).
SEARCH_LIMIT = 25


class BrowseDockerHubView(APIView):
    """Docker Hub search through the Docker daemon, the same search `docker search` runs. It uses
    the daemon's registry and proxy settings, and needs no Docker Hub URL in this app."""

    permission_classes = (CanManageDocker,)

    def get(self, request):
        q = request.GET.get('q', '').strip()
        if not q:
            return Response({'summary': [], 'q': q})
        with closing(docker_client()) as client:
            try:
                results = client.images.search(q, limit=SEARCH_LIMIT)
            except docker.errors.APIError as exc:
                return Response({'detail': exc.explanation or str(exc)}, status=502)
        summary = [
            {
                'name': item['name'],
                'description': item.get('description') or '',
                'star_count': item.get('star_count', 0),
                'is_official': bool(item.get('is_official')),
            }
            for item in results
        ]
        return Response({'summary': summary, 'q': q})


class ContainersListView(APIView):
    permission_classes = (CanManageDocker,)

    def get(self, request, format=None):
        with closing(docker_client()) as client:
            containers = [
                {
                    'id': container.id,
                    'name': container.name,
                    'status': container.status,
                    'command': container.attrs['Config'].get('Cmd'),
                    'short_id': container.short_id,
                    'image_tag': container.image.tags[0] if container.image.tags else None,
                }
                for container in client.containers.list(all=True)
            ]
            return Response({'containers': containers, 'info': client.info()})


class ImagesListView(APIView):
    permission_classes = (CanManageDocker,)

    def get(self, request, format=None):
        with closing(docker_client()) as client:
            images = [
                {
                    'id': image.id.removeprefix('sha256:'),
                    'size': round(image.attrs['Size'] / 1048576, 2),  # MiB
                    'short_id': image.short_id.removeprefix('sha256:'),
                    'name': image.tags[0] if image.tags else None,
                }
                for image in client.images.list()
            ]
            return Response({'images': images, 'info': client.info()})


class ConsoleView(APIView):
    """What the console page shows above the terminal."""

    permission_classes = (CanManageDocker,)

    def get(self, request, id, action):
        with closing(docker_client()) as client:
            try:
                container = client.containers.get(id)
            except docker.errors.NotFound:
                raise NotFound(f"No such container: {id}")
        commands = container.attrs['Config']['Cmd']
        return Response({
            'id': id,
            'container_name': container.name,
            'image': container.attrs['Config']['Image'],
            'short_id': container.short_id,
            'command': ' '.join(commands) if commands else None,
            'action': action,
        })


class ImageRequest(serializers.Serializer):
    image_id = serializers.CharField()


class ContainerActionRequest(serializers.Serializer):
    id = serializers.CharField()
    cmd = serializers.ChoiceField(choices=list(CONTAINER_ACTIONS))


def queue(task, *args) -> Response:
    """Hand the Docker call to the RQ worker; the page hears back over the notifications socket."""
    return Response({"task_id": task.delay(*args).id})


@api_view(['POST'])
@permission_classes([CanManageDocker])
def run_image(request):
    data = ImageRequest(data=request.data)
    data.is_valid(raise_exception=True)
    return queue(run_image_task, data.validated_data['image_id'])


@api_view(['POST'])
@permission_classes([CanManageDocker])
def remove_image(request):
    data = ImageRequest(data=request.data)
    data.is_valid(raise_exception=True)
    return queue(remove_image_task, data.validated_data['image_id'])


@api_view(['POST'])
@permission_classes([CanManageDocker])
def start_stop_remove(request):
    data = ContainerActionRequest(data=request.data)
    data.is_valid(raise_exception=True)
    container_id, cmd = data.validated_data['id'], data.validated_data['cmd']
    # The Containers page swaps the row's buttons for "Waiting" until the job reports back.
    notify(
        "WAITING",
        f"Waiting [{container_id[:8]}] for the task to complete [{cmd}]",
        {"container_id": container_id, "cmd": cmd},
    )
    return queue(container_action_task, container_id, cmd)
