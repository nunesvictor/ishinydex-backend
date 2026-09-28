from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections

from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


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

        # A conexão do próprio Django com o banco impediria o DROP.
        db_connection.close()

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

            # Identifier: nomes como "django-pokedex" precisam de aspas.
            # WITH (FORCE) encerra conexões remanescentes (PostgreSQL 13+).
            db_identifier = sql.Identifier(db_name)
            cursor.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE);").format(
                    db_identifier
                )
            )
            cursor.execute(sql.SQL("CREATE DATABASE {};").format(db_identifier))

            cursor.close()
            conn.close()

            call_command("migrate")
            call_command("createsuperuser", interactive=False)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao recriar banco: {e}"))
