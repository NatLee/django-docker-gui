import uuid
import json
import asyncio
import select
import base64

import docker

from asgiref.sync import sync_to_async
from asgiref.sync import async_to_sync

from django.contrib.auth.models import User

from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from channels.layers import get_channel_layer
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import StopConsumer

import logging
logger = logging.getLogger(__name__)

class ConsoleConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.docker_socket = None
        self.group_name = 'console'

        subprotocol_container = None
        token = None

        # Check for subprotocols
        if self.scope['subprotocols']:
            try:
                for protocol in self.scope['subprotocols']:
                    if protocol.startswith('token.'):
                        # Extract token from subprotocol
                        base64_encoded_token = protocol.split('.', 1)[1]
                        # Decode token
                        token = base64.b64decode(base64_encoded_token).decode()
                    elif protocol.startswith('container.'):
                        # Use the `auth` ticket as the subprotocol
                        subprotocol_container = protocol
            except Exception as e:
                logger.error(f"Error parsing subprotocols: {e}")
                await self.close(code=4000)
                return
            if not token or not subprotocol_container:
                logger.error("Missing required subprotocols")
                await self.close(code=4000)
                return
        else:
            logger.error("No subprotocols provided")
            await self.close(code=4000)
            return

        try:
            # Verify JWT token
            access_token = AccessToken(token)
            # Get user from token
            user = await sync_to_async(User.objects.get)(id=access_token['user_id'])
        except User.DoesNotExist:
            print(f"User not found")
            await self.close(code=4001)
            raise StopConsumer("User Authentication failed")
        except (InvalidToken, TokenError) as e:
            print(f"Token invalid: {e}")
            await self.close(code=4001)
            raise StopConsumer("Token Authentication failed")

        await self.accept(subprotocol_container)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        print(f"[{self.group_name}][{self.channel_name}] connected.")

    async def disconnect(self, code):
        print(f"[{self.group_name}][{self.channel_name}] disconnected.")
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.cleanup()

    async def cleanup(self):
        session_data = await sync_to_async(self.scope["session"].load)()
        if session_data:
            container_id = session_data.get('id')
            exec_id = session_data.get('exec_id')
            pid_path = session_data.get('pid')
            if exec_id:
                try:
                    await self.kill_process(container_id, pid_path)
                    await self.delete_pid_file(container_id, pid_path)
                except Exception as e:  # Consider more specific error handling
                    print(f"Error in exec command: {e}")

    @sync_to_async
    def kill_process(self, container_id, pid_path):
        client = docker.APIClient()
        kill_command = f'kill $(cat {pid_path})'
        print(f'Killing process with command: {kill_command}')
        try:
            kill_exec_id = client.exec_create(container_id, cmd=kill_command)['Id']
            client.exec_start(kill_exec_id, detach=False)
        except docker.errors.APIError as e:
            print(f"Error in exec command: {e}")

    @sync_to_async
    def delete_pid_file(self, container_id, pid_path):
        client = docker.APIClient()
        delete_pid_command = f'rm -f {pid_path}'
        print(f'Deleting PID file with command: {delete_pid_command}')
        delete_exec_id = client.exec_create(container_id, cmd=delete_pid_command)['Id']
        client.exec_start(delete_exec_id, detach=False)

    async def receive(self, text_data):
        message = json.loads(text_data)
        # Route message to appropriate handler
        action = message.get('action')
        payload = message.get('payload')
        if action == 'shell':
            container_id = payload["Id"]
            await self.start_shell(container_id)
        elif action == 'attach':
            container_id = payload["Id"]
            await self.start_attach(container_id)
        elif action == 'pty_input':
            await self.pty_input(payload)

    async def start_shell(self, container_id):
        client = docker.APIClient()
        container_status = self.get_container_status(container_id)
        if container_status != "running":
            await self.close()
            return
        # Generate a unique filename using UUID
        unique_pid_file = f"/tmp/_process_{uuid.uuid4()}.pid"
        exec_instance = client.exec_create(
            container_id,
            cmd=f'sh -c "echo $$ > {unique_pid_file}; exec /bin/bash"',
            stdin=True, tty=True, stderr=True, stdout=True
        )
        exec_id = exec_instance['Id']

        self.docker_socket = self.get_docker_socket(exec_id)
        await self.save_session(container_id, exec_id, unique_pid_file)
        # Start the background task to read and forward the output
        asyncio.create_task(self.read_and_forward_output())

    async def start_attach(self, container_id):
        client = docker.APIClient()
        # check if container is running
        container_status = self.get_container_status(container_id)
        if container_status != "running":
            await self.close()
            return
        self.docker_socket = client.attach_socket(
            container_id,
            params={'stdin': 1, 'stream': 1,'stdout':1,'stderr':1}
        )
        asyncio.create_task(self.read_and_forward_output())

    def get_docker_socket(self, exec_id):
        client = docker.APIClient()
        return client.exec_start(exec_id=exec_id, detach=False, socket=True)

    async def read_and_forward_output(self):
        while True:
            # non-blocking wait for output
            await asyncio.sleep(0.01)
            timeout_sec = 0
            (data_ready, _, _) = select.select([self.docker_socket], [], [], timeout_sec)
            if data_ready:
                output = self.docker_socket._sock.recv(1024)
                if output == b'':
                    # disconnect when we stop receiving data
                    await self.close()
                # Forward the output to the WebSocket
                text_data = output.decode('cp437')[8:]
                await self.send(text_data=text_data)

    async def pty_input(self, payload):
        session_data = await sync_to_async(self.scope["session"].load)()
        exec_id = session_data.get('exec_id')
        # Send the input to the docker socket
        await sync_to_async(self.docker_socket._sock.send)(payload["input"].encode())

    def get_container_status(self, container_id):
        client = docker.APIClient()
        return client.containers(all=True, filters={'id': container_id})[0]["State"]

    async def save_session(self, container_id, exec_id, unique_pid_file):
        # Serialize the docker_socket before saving it if necessary
        session_data = {
            'id': container_id,
            'exec_id': exec_id,
            'pid': unique_pid_file
        }
        self.scope["session"].update(session_data)
        await sync_to_async(self.scope["session"].save)()

class PullConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.docker_socket = None
        self.group_name = 'pull-image'
        await self.accept()
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        print(f"[{self.group_name}][{self.channel_name}] connected.")

    async def disconnect(self, code):
        print(f"[{self.group_name}][{self.channel_name}] disconnected.")
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        message = json.loads(text_data)
        # Route message to appropriate handler
        action = message.get('action')
        payload = message.get('payload')
        if action == 'pull_image':
            image_name = payload.get('image', '')
            image_version = payload.get('version', 'lastest')
            if image_name and image_version:
                await self.pull_image_input(image_name, image_version)

    async def send_pull_image_output(self, status, progress):
        # Call this method when you want to send a "pull_image_output" message
        await self.send(text_data=json.dumps({
            'status': status,
            'progress': progress
        }))

    async def pull_image_input(self, image_name, image_version):
        client = docker.APIClient()
        try:
            x = client.pull(image_name, stream=True,decode=True,tag=image_version)
        except docker.errors.APIError as err:
            print(f"[{type(err)}] {str(err)}")
            await self.send_pull_image_output(str(err), "")
            #useless sleep
            await asyncio.sleep(3)
            self.close()
            return

        for item in x:
            if "progress" not in item:
                item["progress"] = ""
            if "errorDetail" in item:
                item["status"] = item["errorDetail"]["message"]

            await self.send_pull_image_output(
                status=item["status"],
                progress=item["progress"]
            )

        await asyncio.sleep(1.5)
        await self.close()

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = 'notifications'  # Can be dynamic based on path
        self.room_group_name = f'group_{self.room_name}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from room group
    async def send_notification(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))


def send_notification_to_group(message):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'group_notifications',  # Must match the group name used in your consumer
        {
            'type': 'send_notification',
            'message': message
        }
    )

