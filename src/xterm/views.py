import uuid
import select
import json

import docker
import requests
import django_rq

from django.shortcuts import render, redirect
from django.http import JsonResponse

from xterm.task import *


import socketio
sio = socketio.Server(async_mode='eventlet')

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

# ======================================================

def read_and_forward_output(sid):
    print(f'[{sid[:8]}] start background task!')
    # get socket object
    docker_socket = sio.get_session(sid)['socket']
    while True:
        sio.sleep(0.01)
        timeout_sec = 0
        (data_ready, _, _) = select.select([docker_socket], [], [], timeout_sec)
        if data_ready:
            output = docker_socket._sock.recv(1024)
            # check if client disconnected
            if output == b'':
                sio.disconnect(sid)
                return 

            # decode("cp437") ; to decode vim's output
            sio.emit("pty_output", {"output": output.decode("cp437")},room=sid)


@sio.event
def pty_input(sid, message):
    # get socket object 
    docker_socket = sio.get_session(sid)['socket']
    docker_socket._sock.send(message["input"].encode())

@sio.event
def disconnect_request(sid):
    sio.disconnect(sid)

@sio.event
def shell(sid, message):
    print(f'[{sid[:8]}] start a new shell!')
    client = docker.APIClient()

    container_id = message["Id"]

    # Check if the container is running
    container_status = client.containers(all=True, filters={'id': container_id})[0]["State"]
    if container_status != "running":
        sio.disconnect(sid)
        return

    # Generate a unique filename using UUID
    unique_pid_file = f"/tmp/_process_{uuid.uuid4()}.pid"

    # Create a new exec instance in the container with a shell
    exec_instance = client.exec_create(
        container_id,
        cmd=f'sh -c "echo $$ > {unique_pid_file}; exec /bin/bash"',
        stdin=True, tty=True, stderr=True, stdout=True
    )
    exec_id = exec_instance['Id']

    # Start the exec instance and get the socket
    docker_socket = client.exec_start(exec_id=exec_id, detach=False, socket=True)

    # Save the socket object and exec ID to the session
    sio.save_session(sid, {
        'socket': docker_socket,
        'id': container_id,
        'exec_id': exec_id,
        'pid': unique_pid_file
    })
    sio.start_background_task(target=read_and_forward_output(sid))

@sio.event
def attach(sid, message):
    print(f'Client [{sid}] start a new shell!')
    client = docker.APIClient()
    # check if container is running
    if client.containers(all=True,filters={'id':message["Id"]})[0]["State"] != "running":
        sio.disconnect(sid)
        return
    socket = client.attach_socket(message["Id"], params={'stdin': 1, 'stream': 1,'stdout':1,'stderr':1})
    # save socket object to session    
    sio.save_session(sid, {
        'socket': socket,
        "id":message["Id"]
    })
    sio.start_background_task(target=read_and_forward_output(sid))

@sio.event
def pull_image_input(sid,message):
    client = docker.APIClient()
    try:
        x = client.pull(message["image"], stream=True,decode=True,tag=message["version"])
    except docker.errors.APIError as err:
        print(f"[{type(err)}] {str(err)}")
        sio.emit("pull_image_output", {"status": str(err), "progress": ""},room=sid)

        #useless sleep, i just want the user to read the error message before redirection happens
        sio.sleep(3)
        sio.disconnect(sid)
        return

    for item in x:
        if "progress" not in item:
            item["progress"] = ""
        if "errorDetail" in item:
            item["status"] = item["errorDetail"]["message"]

        sio.emit("pull_image_output", {"status": item["status"], "progress": item["progress"]},room=sid)
        sio.sleep(0)

    sio.sleep(1.5)
    sio.disconnect(sid)

@sio.event
def connect(sid, environ):
    print(f'[{sid[:8]}] connected.')

@sio.event
def disconnect(sid):
    print(f'[{sid[:8]}] disconnected.')
    # Retrieve session data
    session = sio.get_session(sid)
    if session:
        client = docker.APIClient()
        container_id = session.get('id')
        exec_id = session.get('exec_id')
        pid_path = session.get('pid')
        if exec_id:
            try:
                # Send a command to kill the process
                kill_command = f'kill $(cat {pid_path})'
                print(f'[{sid[:8]}] destroy ->  {kill_command}')
                kill_exec_id = client.exec_create(container_id, cmd=kill_command)['Id']
                client.exec_start(kill_exec_id, detach=False)

                # Attempt to delete PID file
                delete_pid_command = f'rm -f {pid_path}'
                delete_exec_id = client.exec_create(container_id, cmd=delete_pid_command)['Id']
                client.exec_start(delete_exec_id, detach=False)
            except docker.errors.APIError as e:
                print(f"Error in exec command: {e}")

