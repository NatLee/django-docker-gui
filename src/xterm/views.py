import json

import docker
import requests
import django_rq

from django.shortcuts import render, redirect
from django.http import JsonResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny

from xterm.task import run_image_task
from xterm.task import remove_image_task
from xterm.task import run_container_task
from xterm.task import remove_container_task
from xterm.task import stop_container_task
from xterm.task import restart_container_task

class Index(APIView):
    permission_classes = (AllowAny,)
    swagger_schema = None
    def get(self, request):
        response = redirect('/login')
        return response

class Containers(APIView):
    permission_classes = (AllowAny,)
    swagger_schema = None
    def get(self, request):
        return render(request, 'containers.html')

class Images(APIView):
    permission_classes = (AllowAny,)
    swagger_schema = None
    def get(self, request):
        return render(request, 'images.html')

class Console(APIView):
    permission_classes = (AllowAny,)
    swagger_schema = None
    def get(self, request, id):
        return render(request, 'console.html')

class BrowseDockerHub(APIView):
    permission_classes = (AllowAny,)
    swagger_schema = None
    def get(self, request):
        return render(request, 'browse.html')

class BrowseDockerHubView(APIView):
    permission_classes = (IsAuthenticated,)
    def get(self, request):
        page_number = request.GET.get('page','1')
        q = request.GET.get('q','')

        url = f'https://hub.docker.com/api/content/v1/products/search?page={page_number}&page_size=15&q={q}&type=image'
        headers = {'Search-Version': 'v3'}
        page = requests.get(url, headers=headers)
        summary = page.json()['summaries']
        return Response({
            'summary': summary,
            'q': q
        })

class ContainersListView(APIView):
    permission_classes = (IsAuthenticated,)
    def get(self, request, format=None):
        client = docker.from_env()
        containers = client.containers.list(all=True)

        # Serialize the container data
        container_data = []
        for container in containers:
            image_tag = None
            image_tags = container.image.tags
            if image_tags:
                image_tag = image_tags[0]

            container_info = {
                'id': container.id,
                'name': container.name,
                'status': container.status,
                'command': container.attrs['Config'].get('Cmd', None),
                'short_id': container.short_id,
                'image_tag': image_tag
            }
            container_data.append(container_info)

        # Serialize additional information if necessary
        info = client.info()  # Transform this as needed

        return Response({
            'containers': container_data,
            'info': info  # Ensure this is in a serializable format
        })

class ImagesListView(APIView):
    permission_classes = (IsAuthenticated,)
    def get(self, request, format=None):
        client = docker.from_env()
        images = client.images.list()

        # Serialize the image data
        image_data = []
        for image in images:
            name = image.tags[0] if image.tags else None
            image_info = {
                'id': image.id[7:],
                'size': round(image.attrs['Size']/1048576, 2),
                'short_id': image.short_id[7:],
                'name': name
            }
            image_data.append(image_info)

        # Serialize additional information if necessary
        info = client.info()  # Transform this as needed

        return Response({
            'images': image_data,
            'info': info  # Ensure this is in a serializable format
        })

class ConsoleView(APIView):
    permission_classes = (IsAuthenticated,)
    def get(self, request, id, action):
        client = docker.from_env()
        container = client.containers.get(id)
        commands = container.attrs['Config']['Cmd']
        if not commands:
            command = None
        else:
            command = ' '.join(commands)

        return Response({
            'id': id,
            'container_name': container.attrs['Name'][1:],  # Remove the leading "/"
            'image': container.attrs['Config']['Image'],
            'short_id': container.short_id,
            'command': command,
            'action': action
        })

@api_view(['POST'])
def run_image(request):
    image_id = request.data['image_id']
    job = run_image_task.delay(image_id)  # Queue the job
    return JsonResponse({"task_id": job.id})  # Use job.id to get the job ID

@api_view(['POST'])
def remove_image(request):
    image_id = request.data['image_id']
    job = remove_image_task.delay(image_id)
    return JsonResponse({"task_id": job.id})  # Use job.id here as well

@api_view(['POST'])
def start_stop_remove(request):
    cmd = request.data['cmd']
    _id = request.data['id']

    job = None

    if cmd == "start":
        job = run_container_task.delay(_id)
    elif cmd == "stop":
        job = stop_container_task.delay(_id)
    elif cmd == "remove":
        job = remove_container_task.delay(_id)
    elif cmd == "restart":
        job = restart_container_task.delay(_id)

    if job:
        return JsonResponse({"task_id": job.id})

    return JsonResponse({"task_id": None})

def check_progress(request, task_id):
    queue = django_rq.get_queue('default')
    job = queue.fetch_job(task_id)
    details = 'No details available.'

    # Check if job exists
    if job is None:
        state = 'NOT FOUND'
        details = 'No job with the provided ID was found.'
        return JsonResponse({
            'state': state,
            'details': details
        })

    # Check job status
    if job.is_finished:
        state = 'FINISHED'
        details = job.result
    elif job.is_queued:
        state = 'QUEUED'
        details = 'Job is queued.'
    elif job.is_started:
        state = 'STARTED'
        details = 'Job is in progress.'
    elif job.is_failed:
        state = 'FAILED'
        details = str(job.exc_info)  # Extract exception info if job failed
    else:
        state = 'UNKNOWN'
        details = 'The job state is unknown.'

    response_data = {
        'state': state,
        'details': details
    }
    return JsonResponse(response_data)


