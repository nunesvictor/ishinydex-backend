import os
import subprocess
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _

APP_HOME = os.getenv("APP_HOME", "/home/guest/django-pokedex")
APP_NAME = os.getenv("APP_NAME", "django-pokedex")
POSTGRES_DB = os.getenv("POSTGRES_DB", APP_NAME)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")

timestamp = datetime.now().strftime("%Y%m%d%H%M")
backup_filename = f"{APP_HOME}/backups/dump-{POSTGRES_DB}-{timestamp}.backup"


class Command(BaseCommand):
    help = _("Backup the app's database on the backups folder.")

    def handle(self, *args, **options):
        command = [
            "pg_dump",
            "-h",
            POSTGRES_HOST,
            "-p",
            POSTGRES_PORT,
            "-U",
            POSTGRES_USER,
            "-d",
            POSTGRES_DB,
            "-Fc",
            "-Z",
            "8",
            "-f",
            backup_filename,
        ]

        self.stdout.write(
            f"[{APP_NAME}] Creating custom backup (comp: 8) for `{POSTGRES_DB}`..."
        )

        env_config = os.environ.copy()
        env_config["PGPASSWORD"] = POSTGRES_PASSWORD

        try:
            # Clear old auth sessions before dumping the database
            call_command("clearsessions")

            # Dumps the database
            result = subprocess.run(
                command,
                capture_output=True,
                env=env_config,
                text=True,
            )

            if result.returncode == 0:
                self.stdout.write(
                    f"[{APP_NAME}] Database `{POSTGRES_DB}` dumped to {backup_filename}"
                )
            else:
                self.stderr.write(
                    f"[{APP_NAME}] Failed to dump database `{POSTGRES_DB}`"
                )

                self.stderr.write(f"Error:\n{result.stderr}")
        except FileNotFoundError:
            self.stderr.write(f"[{APP_NAME}] Error: command 'pg_dump' not found")
