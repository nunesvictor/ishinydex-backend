from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class MigrationsTests(TestCase):
    def test_models_have_no_pending_migrations(self):
        out = StringIO()

        try:
            call_command("makemigrations", "--check", "--dry-run", stdout=out)
        except SystemExit:
            self.fail(f"Há alterações de model sem migração:\n{out.getvalue()}")
