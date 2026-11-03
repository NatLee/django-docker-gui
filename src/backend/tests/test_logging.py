import io
import logging
from unittest import mock

from django.test import SimpleTestCase


class LoggingTests(SimpleTestCase):
    def console_handler(self):
        return next(h for h in logging.getLogger().handlers if isinstance(h, logging.StreamHandler))

    def test_library_loggers_reach_the_console(self):
        # The old config disabled every logger that existed before it ran, which hid Daphne's
        # "Exception inside application" messages.
        stream = io.StringIO()
        with mock.patch.object(self.console_handler(), "stream", stream):
            logging.getLogger("daphne.server").error("boom from a library")
            logging.getLogger("xterm.consumers").warning("boom from the app")
        self.assertIn("ERROR] daphne.server: boom from a library", stream.getvalue())
        self.assertIn("WARNING] xterm.consumers: boom from the app", stream.getvalue())
