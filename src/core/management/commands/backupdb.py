import os
import subprocess
from datetime import datetime

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _

APP_NAME = os.getenv("APP_NAME", "ishinydex")


def pg_connection_args(db: dict) -> tuple[list[str], dict[str, str]]:
    """Argumentos de conexão e ambiente (PGPASSWORD) para pg_dump/pg_restore."""
    args = [
        "-h",
        db["HOST"],
        "-p",
        str(db["PORT"]),
        "-U",
        db["USER"],
        "-d",
        db["NAME"],
    ]
    env = os.environ.copy()
    env["PGPASSWORD"] = db["PASSWORD"]

    return args, env


class Command(BaseCommand):
    help = _("Backup the app's database on the backups folder.")

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        backup_filename = settings.BACKUPS_DIR / f"dump-{db['NAME']}-{timestamp}.backup"

        connection_args, env = pg_connection_args(db)
        command = [
            "pg_dump",
            *connection_args,
            "-Fc",
            "-Z",
            "8",
            "-f",
            str(backup_filename),
        ]

        self.stdout.write(
            f"[{APP_NAME}] Creating custom backup (comp: 8) for `{db['NAME']}`..."
        )

        try:
            # Clear old auth sessions before dumping the database
            call_command("clearsessions")

            # Dumps the database
            result = subprocess.run(command, capture_output=True, env=env, text=True)

            if result.returncode == 0:
                self.stdout.write(
                    f"[{APP_NAME}] Database `{db['NAME']}` dumped to {backup_filename}"
                )
            else:
                self.stderr.write(
                    f"[{APP_NAME}] Failed to dump database `{db['NAME']}`"
                )

                self.stderr.write(f"Error:\n{result.stderr}")
        except FileNotFoundError:
            self.stderr.write(f"[{APP_NAME}] Error: command 'pg_dump' not found")
