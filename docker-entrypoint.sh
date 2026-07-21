#!/bin/bash
#
# Inicia o serviço do cron e inicializa o banco de dados
# autor: Victor Guimarães Nunes <nunessvictorr@gmail.com>
set +euo pipefail

if [[ "${REPLICA:-0}" == "1" ]] ; then
    echo "[${APP_NAME}] Installing crontab..."
    mkdir -p "${APP_HOME}/logs" && { \
        echo "APP_HOME=${APP_HOME}"; \
        echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"; \
        echo "REPLICA=${REPLICA}"; \
        echo ""; \
        # Add Crontab entries here, for example:
        # $JOB_SYNC_DEX_ENTRIES     && echo "10 0 * * * ${APP_HOME}/run_scheduled_job.sh sync_dex_entries"; \
    } | crontab -

    echo "[${APP_NAME}] Starting cron service..."
    /usr/sbin/cron -f &
fi

db_init_action="${APP_INITDB:-0}"

if [[ "$db_init_action" != "0" ]]; then
    case "$db_init_action" in
        "recreate")
            echo "[${APP_NAME}] Recreating database..."
            python manage.py recreatedb

            echo "[${APP_NAME}] Recreating migrations..."
            for app in $PROJECT_APPS; do
                rm -rf "$app/migrations"
            done
            python manage.py makemigrations $PROJECT_APPS

            echo "[${APP_NAME}] Migrating database..."
            python manage.py migrate

            if [[ "${APP_CREATE_SUPERUSER:-0}" == "1" ]] ; then
                echo "[${APP_NAME}] Check superuser credentials..."
                python manage.py createsuperuser --no-input 2> /dev/null
            fi
            ;;
        "restore")
            echo "[${APP_NAME}] Restoring database..."
            python manage.py restoredb
            ;;
        *)
            echo "[${APP_NAME}] Invalid value for env APP_INITDB ('$db_init_action'), values must be [recreate|restore], aborting..."
            ;;
    esac
fi

exec "$@"
