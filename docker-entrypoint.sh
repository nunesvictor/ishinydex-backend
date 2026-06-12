#!/bin/bash
#
# Inicia o serviço do cron
# autor: Victor Guimarães Nunes <nunessvictorr@gmail.com>
set +euo pipefail

if [[ $REPLICA == "1" ]] ; then
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

if [[ $RECREATE_DB == "1" ]] ; then
    echo "[${APP_NAME}] Recreating database..."
    python manage.py recreatedb

    echo "[${APP_NAME}] Recreating migrations..."
    rm -rf core/migrations pokedex/migrations
    python manage.py makemigrations core pokedex

    echo "[${APP_NAME}] Migrating database..."
    python manage.py migrate

    echo "[${APP_NAME}] Check superuser credentials..."
    python manage.py createsuperuser --no-input 2> /dev/null
fi

exec "$@"
