from types import SimpleNamespace
from unittest import mock

import docker
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken

from xterm.tests.fakes import FakeClient


def fake_container(id, name, status, cmd, tags):
    return SimpleNamespace(id=id, name=name, status=status, short_id=id[:10], attrs={"Config": {"Cmd": cmd, "Image": "img"}},
                           image=SimpleNamespace(tags=tags))


class ApiTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("member", password="pw")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(user)}"}
        self.client_docker = FakeClient()
        self.client_docker.info = lambda: {"Containers": 2}
        patcher = mock.patch("xterm.views.docker_client", return_value=self.client_docker)
        patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, url, data):
        return self.client.post(url, data, content_type="application/json", **self.auth)

    def test_container_list(self):
        self.client_docker.containers.list = mock.Mock(return_value=[
            fake_container("a" * 64, "web", "running", ["nginx", "-g", "daemon off;"], ["nginx:1.27", "nginx:latest"]),
            fake_container("b" * 64, "old", "exited", None, []),
        ])
        response = self.client.get("/api/containers", **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"containers": [
            {"id": "a" * 64, "name": "web", "status": "running", "command": ["nginx", "-g", "daemon off;"],
             "short_id": "a" * 10, "image_tag": "nginx:1.27"},
            {"id": "b" * 64, "name": "old", "status": "exited", "command": None, "short_id": "b" * 10, "image_tag": None},
        ], "info": {"Containers": 2}})
        self.client_docker.containers.list.assert_called_once_with(all=True)
        self.assertTrue(self.client_docker.closed)

    def test_image_list(self):
        image = SimpleNamespace(id="sha256:" + "c" * 64, short_id="sha256:cccccccccc", tags=["alpine:3.22"],
                                attrs={"Size": 3_880_000})
        self.client_docker.images.list = mock.Mock(return_value=[image])
        response = self.client.get("/api/images", **self.auth)
        self.assertEqual(response.json()["images"], [{"id": "c" * 64, "size": 3.7, "short_id": "cccccccccc", "name": "alpine:3.22"}])

    def test_console_info_and_missing_container(self):
        self.client_docker.containers.get = mock.Mock(return_value=fake_container("d" * 64, "web", "running", ["bash"], []))
        response = self.client.get("/api/console/shell/" + "d" * 64, **self.auth)
        self.assertEqual(response.json(), {"id": "d" * 64, "container_name": "web", "image": "img",
                                           "short_id": "d" * 10, "command": "bash", "action": "shell"})
        self.client_docker.containers.get.side_effect = docker.errors.NotFound("nope")
        with self.assertLogs("django.request", "WARNING"):
            response = self.client.get("/api/console/shell/missing", **self.auth)
        self.assertEqual(response.status_code, 404)  # was a 500

    @mock.patch("xterm.views.notify")
    @mock.patch("xterm.task.container_action_task.delay", return_value=SimpleNamespace(id="job-1"))
    def test_container_action_queues_the_job_and_says_waiting(self, delay, notify):
        response = self.post("/api/containers/start-stop-remove", {"id": "0123456789abcdef", "cmd": "restart"})
        self.assertEqual(response.json(), {"task_id": "job-1"})
        delay.assert_called_once_with("0123456789abcdef", "restart")
        notify.assert_called_once_with(
            "WAITING", "Waiting [01234567] for the task to complete [restart]",
            {"container_id": "0123456789abcdef", "cmd": "restart"},
        )

    @mock.patch("xterm.views.notify")
    @mock.patch("xterm.task.container_action_task.delay")
    def test_bad_container_actions_are_400_and_queue_nothing(self, delay, notify):
        for body in ({"id": "x"}, {"cmd": "stop"}, {"id": "x", "cmd": "format"}, {"id": "", "cmd": "stop"}):
            with self.subTest(body=body), self.assertLogs("django.request", "WARNING"):
                self.assertEqual(self.post("/api/containers/start-stop-remove", body).status_code, 400)
        delay.assert_not_called()
        notify.assert_not_called()

    def test_image_jobs(self):
        for url, job in (("/api/images/run", "run_image_task"), ("/api/images/remove", "remove_image_task")):
            with self.subTest(url=url), mock.patch(f"xterm.task.{job}.delay", return_value=SimpleNamespace(id="j")) as delay:
                self.assertEqual(self.post(url, {"image_id": "2e0b81d60597"}).json(), {"task_id": "j"})
                delay.assert_called_once_with("2e0b81d60597")
                with self.assertLogs("django.request", "WARNING"):
                    self.assertEqual(self.post(url, {}).status_code, 400)  # was a KeyError, 500
