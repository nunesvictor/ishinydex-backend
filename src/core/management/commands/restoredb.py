import glob
import os
import subprocess

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

APP_HOME = os.getenv("APP_HOME", "/home/guest/ishinydex-backend")
APP_NAME = os.getenv("APP_NAME", "ishinydex")
POSTGRES_DB = os.getenv("POSTGRES_DB", APP_NAME)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")

BACKUPS_DIR = f"{APP_HOME}/backups"


class Command(BaseCommand):
    help = _("Restores the database using the newest .backup file.")

    def handle(self, *args, **options):
        search_pattern = os.path.join(BACKUPS_DIR, "*.backup")
        backup_files = glob.glob(search_pattern)

        if not backup_files:
            self.stderr.write(
                f"[{APP_NAME}] Error: No .backup files found in {BACKUPS_DIR}"
            )
            return

        last_bkp = max(backup_files, key=os.path.getmtime)

        self.stdout.write(
            f"[{APP_NAME}] Restoring `{POSTGRES_DB}` from backup: "
            f'"{os.path.basename(last_bkp)}"...'
        )

        comando = [
            "pg_restore",
            "-h",
            POSTGRES_HOST,
            "-p",
            POSTGRES_PORT,
            "-U",
            POSTGRES_USER,
            "-d",
            POSTGRES_DB,
            "-c",
            "--if-exists",
            last_bkp,
        ]

        env_config = os.environ.copy()
        env_config["PGPASSWORD"] = POSTGRES_PASSWORD

        try:
            resultado = subprocess.run(
                comando, env=env_config, capture_output=True, text=True
            )

            if resultado.returncode == 0:
                self.stdout.write(
                    f"[{APP_NAME}] Database `{POSTGRES_DB}` successfully restored!"
                )
            else:
                self.stderr.write(
                    f"[{APP_NAME}] Failed to restore database `{POSTGRES_DB}`"
                )
                self.stderr.write(f"Error:\n{resultado.stderr}")

        except FileNotFoundError:
            self.stderr.write(f"[{APP_NAME}] Error: command 'pg_restore' not found")
