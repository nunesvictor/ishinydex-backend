import os
import subprocess
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _

APP_HOME = os.getenv("APP_HOME", "/home/guest/ishinydex-backend")
APP_NAME = os.getenv("APP_NAME", "ishinydex")
POSTGRES_DB = os.getenv("POSTGRES_DB", APP_NAME)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")

timestamp = datetime.now().strftime("%Y%m%d%H%M")
dump_file = f"{APP_HOME}/backups/data-{POSTGRES_DB}-{timestamp}.sql"


class Command(BaseCommand):
    help = _("Dumps the app's data only on the backups folder.")

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
            "-Fp",
            "-a",
            "--inserts",
            "--column-inserts",
            "-f",
            dump_file,
        ]

        self.stdout.write(f"[{APP_NAME}] Creating data dump for `{POSTGRES_DB}`...")

        env_config = os.environ.copy()
        env_config["PGPASSWORD"] = POSTGRES_PASSWORD

        try:
            # Clear old auth sessions before dumping the database
            call_command("clearsessions")

            # Create the data dump
            result = subprocess.run(
                command,
                capture_output=True,
                env=env_config,
                text=True,
            )

            if result.returncode == 0:
                self.stdout.write(
                    f"[{APP_NAME}] Data from `{POSTGRES_DB}` dumped: {dump_file}"
                )
            else:
                self.stderr.write(
                    f"[{APP_NAME}] Failed to dump data from `{POSTGRES_DB}`"
                )

                self.stderr.write(f"Error:\n{result.stderr}")
        except FileNotFoundError:
            self.stderr.write(f"[{APP_NAME}] Error: command 'pg_dump' not found")
