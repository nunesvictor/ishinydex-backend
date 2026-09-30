import os
import subprocess

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from core.management.base import BaseCommand

from .backupdb import APP_NAME, pg_connection_args


class Command(BaseCommand):
    help = _("Restores the database using the newest .backup file.")

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        backup_files = list(settings.BACKUPS_DIR.glob("*.backup"))

        if not backup_files:
            self.stderr.write(
                f"[{APP_NAME}] Error: No .backup files found in {settings.BACKUPS_DIR}"
            )
            return

        last_bkp = max(backup_files, key=os.path.getmtime)

        self.stdout.write(
            f"[{APP_NAME}] Restoring `{db['NAME']}` from backup: "
            f'"{last_bkp.name}"...'
        )

        connection_args, env = pg_connection_args(db)
        command = ["pg_restore", *connection_args, "-c", "--if-exists", str(last_bkp)]

        try:
            result = subprocess.run(command, env=env, capture_output=True, text=True)

            if result.returncode == 0:
                self.stdout.write(
                    f"[{APP_NAME}] Database `{db['NAME']}` successfully restored!"
                )
            else:
                self.stderr.write(
                    f"[{APP_NAME}] Failed to restore database `{db['NAME']}`"
                )
                self.stderr.write(f"Error:\n{result.stderr}")

        except FileNotFoundError:
            self.stderr.write(f"[{APP_NAME}] Error: command 'pg_restore' not found")
