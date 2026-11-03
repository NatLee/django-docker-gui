from types import SimpleNamespace
from unittest import mock

import docker
from django.test import SimpleTestCase

from xterm import task
from xterm.tests.fakes import FakeClient


class FakeContainer:
    def __init__(self, name, fail_with=None, tags=("alpine:3.22",)):
        self.name = name
        self.done = []
        self.fail_with = fail_with
        self.image = SimpleNamespace(tags=list(tags))

    def __getattr__(self, action):  # start(), stop(), restart(), remove()
        def call():
            if self.fail_with:
                raise self.fail_with
            self.done.append(action)
        return call


def conflict(explanation):
    response = SimpleNamespace(status_code=409, reason="Conflict")
    return docker.errors.APIError("409 Client Error", response=response, explanation=explanation)


class JobTests(SimpleTestCase):
    def setUp(self):
        self.client = FakeClient()
        self.notified = []
        patches = [
            mock.patch("xterm.task.docker_client", return_value=self.client),
            mock.patch("xterm.task.notify", side_effect=lambda *a: self.notified.append(a)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_every_container_action_does_it_and_announces_it(self):
        expected = {"start": "STARTED", "stop": "STOPPED", "restart": "RESTARTED", "remove": "REMOVED"}
        self.assertEqual(task.CONTAINER_ACTIONS, expected)
        for action, event in expected.items():
            with self.subTest(action=action):
                container = FakeContainer("web")
                self.client.containers.get = mock.Mock(return_value=container)
                self.notified.clear()
                msg = task.container_action_task(f"id-{action}", action)
                self.client.containers.get.assert_called_once_with(f"id-{action}")
                self.assertEqual(container.done, [action])
                self.assertEqual(msg, f"Container [web] has been {event.lower()}")
                self.assertEqual(self.notified, [(event, msg)])
                self.assertTrue(self.client.closed)

    def test_failures_are_announced_and_still_fail_the_job(self):
        # Before, a failing job sent nothing and the row stayed on "Waiting" for good.
        error = conflict("container is running: stop the container before removing or force remove")
        self.client.containers.get = mock.Mock(return_value=FakeContainer("web", fail_with=error))
        with self.assertRaises(docker.errors.APIError):
            task.container_action_task("0123456789abcdef", "remove")
        self.assertEqual(self.notified, [(
            "FAILED",
            "Could not remove container [0123456789ab]: container is running: stop the container "
            "before removing or force remove",
        )])

    def test_missing_container_is_a_failure_too(self):
        self.client.containers.get = mock.Mock(side_effect=docker.errors.NotFound("No such container: x"))
        with self.assertRaises(docker.errors.NotFound):
            task.container_action_task("x", "start")
        self.assertEqual(self.notified[0][0], "FAILED")
        self.assertIn("No such container: x", self.notified[0][1])

    def test_run_image(self):
        self.client.containers.run = mock.Mock(return_value=FakeContainer("brave_turing"))
        msg = task.run_image_task("2e0b81d60597")
        self.client.containers.run.assert_called_once_with("2e0b81d60597", stdin_open=True, detach=True, tty=True)
        self.assertEqual(msg, "Container [brave_turing] (alpine:3.22) has been created")
        self.assertEqual(self.notified, [("CREATED", msg)])

    def test_run_untagged_image(self):
        self.client.containers.run = mock.Mock(return_value=FakeContainer("x", tags=()))
        self.assertEqual(task.run_image_task("abc"), "Container [x] (none) has been created")

    def test_remove_image_and_its_failure(self):
        self.client.images.remove = mock.Mock()
        self.assertEqual(task.remove_image_task("abc"), "Image [abc] has been removed")
        self.client.images.remove.assert_called_once_with(image="abc")
        self.client.images.remove.side_effect = conflict("image is being used by running container 123")
        with self.assertRaises(docker.errors.APIError):
            task.remove_image_task("abc")
        self.assertEqual(self.notified[-1], ("FAILED", "Could not remove image [abc]: image is being used by running container 123"))
