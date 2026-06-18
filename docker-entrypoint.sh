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

if [[ $DB_INIT != "0" ]]; then
    if [[ $DB_INIT == "recreate" ]] ; then
        echo "[${APP_NAME}] Recreating database..."
        python manage.py recreatedb

        echo "[${APP_NAME}] Recreating migrations..."
        for app in $PROJECT_APPS; do rm -rf "$app/migrations"; done
        python manage.py makemigrations $PROJECT_APPS

        echo "[${APP_NAME}] Migrating database..."
        python manage.py migrate

        echo "[${APP_NAME}] Check superuser credentials..."
        python manage.py createsuperuser --no-input 2> /dev/null
    elif [[ $DB_INIT == "restore" ]] ; then
        echo "[${APP_NAME}] Looking for the latest backup..."
        last_bkp=$(ls -t ../backups/*.backup 2>/dev/null | head -n 1)

        if [[  -n "$last_bkp"  ]]; then
            set -a; source .env; set +a;

            echo "[${APP_NAME}] Restoring \`${POSTGRES_DB:-$APP_NAME}\` from backup: \"$last_bkp\""...
            PGPASSWORD="${POSTGRES_PASSWORD:-postgres}" pg_restore -h ${POSTGRES_HOST:-db} -p ${POSTGRES_PORT:-5432} -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-$APP_NAME} -c --if-exists "$last_bkp"

            case $? in
                0)
                    echo -e "\e[1A[${APP_NAME}] Restoring \`${POSTGRES_DB:-$APP_NAME}\` from backup: \"$last_bkp\"... done!"
                    ;;
                *)
                    echo -e "\e[1A[${APP_NAME}] Restoring \`${POSTGRES_DB:-$APP_NAME}\` from backup: \"$last_bkp\"... failed!"
                    ;;
            esac
        else
            echo "[${APP_NAME}] Backup not found, aborting..."
        fi
    else
        echo "[${APP_NAME}] Invalid value for env DB_INIT, values must be [0|recreate|restore], aborting..."
    fi
fi

exec "$@"
