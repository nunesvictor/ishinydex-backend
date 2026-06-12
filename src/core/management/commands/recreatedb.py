import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections

from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

POSTGRES_DB = os.environ.get("POSTGRES_DB", "ishinydex")


class Command(BaseCommand):
    help = "Derruba e recria o banco de dados padrão."

    def handle(self, *args, **options):
        db_settings = settings.DATABASES["default"]
        db_name = db_settings["NAME"]

        self.stderr.write("+-------------------------------------------+")
        self.stderr.write("|                                           |")
        self.stderr.write("|  WARNING: THE DATABASE WILL BE RECREATED  |")
        self.stderr.write("|                                           |")
        self.stderr.write("+-------------------------------------------+")

        db_connection = connections["default"]
        psycopg2_module = db_connection.Database

        try:
            conn = psycopg2_module.connect(
                dbname="postgres",
                user=db_settings.get("USER"),
                password=db_settings.get("PASSWORD"),
                host=db_settings.get("HOST"),
                port=db_settings.get("PORT"),
            )

            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            cursor.execute(f"DROP DATABASE IF EXISTS {db_name};")
            cursor.execute(f"CREATE DATABASE {db_name};")

            cursor.close()
            conn.close()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao recriar banco: {e}"))
