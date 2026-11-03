from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class MigrationTests(TestCase):
    def test_models_and_committed_migrations_agree(self):
        # The container no longer runs makemigrations at start, so a model change without a
        # committed migration would never reach the database.
        out = StringIO()
        try:
            call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)
        except SystemExit:
            self.fail("models have changes without a migration:\n" + out.getvalue())
