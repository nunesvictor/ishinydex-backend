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

exec "$@"
