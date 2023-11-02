import json

import docker
import requests
import django_rq

from django.shortcuts import render, redirect
from django.http import JsonResponse

from xterm.task import run_image_task
from xterm.task import remove_image_task
from xterm.task import run_container_task
from xterm.task import remove_container_task
from xterm.task import stop_container_task


def index(request):
    response = redirect('/containers')
    return response
        
def containers(request):
    client = docker.from_env()
    return render(
        request,
        'containers.html',
        {'containers':client.containers.list(all=True),'info':client.info()}
    )

def images(request):
    client = docker.from_env()
    return render(request, 'images.html',{'images':client.images.list()})

# to dynamicly update the content of django template without reloading 
# TODO split front from back
def ajax_images(request):
    client = docker.from_env()
    return render(request, 'ajaxImages.html',{'images':client.images.list()})
        
def ajax_containers(request):
    client = docker.from_env()
    return render(request, 'ajaxContainers.html',{'containers':client.containers.list(all=True),'info':client.info()})

def shell_console(request,id):
    client = docker.from_env()
    container = client.containers.get(id)
    return render(request,'console.html',{'id':id, 'container':container, 'action': 'shell'})

def attach_console(request,id):
    client = docker.from_env()
    container = client.containers.get(id)
    return render(request,'console.html',{'id':id, 'container':container, 'action': 'attach'})

def browse(request):
    page_number = request.GET.get('page','1')
    q = request.GET.get('q','')

    url = 'https://hub.docker.com/api/content/v1/products/search?page='+page_number+'&page_size=15&q='+q+'&type=image'
    headers = {'Search-Version': 'v3'}
    page = requests.get(url, headers=headers)
    summary = page.json()['summaries']
    return render(request, 'browse.html', {'summary': summary,'q':q})

def run_image(request):
    if request.method == 'POST':
        image_id = json.load(request)['image_id']
        job = run_image_task.delay(image_id)  # Queue the job
        return JsonResponse({"task_id": job.id})  # Use job.id to get the job ID

def remove_image(request):
    if request.method == 'POST':
        image_id = json.load(request)['image_id']
        job = remove_image_task.delay(image_id)
        return JsonResponse({"task_id": job.id})  # Use job.id here as well

def start_stop_remove(request):
    if request.method == 'POST':
        json_data = json.load(request)
        cmd = json_data['cmd']
        _id = json_data['id']

        if cmd == "start":
            job = run_container_task.delay(_id)
        elif cmd == "stop":
            job = stop_container_task.delay(_id)
        elif cmd == "remove":
            job = remove_container_task.delay(_id)
        return JsonResponse({"task_id": job.id})

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


