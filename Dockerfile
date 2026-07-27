# ==========================================
# STAGE 1: Asset Downloader (Sprites)
# ==========================================
FROM alpine/git:latest AS sprite-builder

WORKDIR /tmp/sprites

RUN git clone --filter=blob:none --no-checkout https://github.com/PokeAPI/sprites.git . && \
    git sparse-checkout init --cone && \
    git sparse-checkout set sprites/pokemon sprites/types && \
    git checkout

# ==========================================
# STAGE 2: Final Application Image
# ==========================================
FROM python:3.14-slim

# 1. Define Arguments and Environment Variables
ARG APP_NAME="ishinydex-backend"
ARG APP_HOME="/home/guest/${APP_NAME}"

ENV HOME=/home/guest \
    DJANGO_SETTINGS_MODULE=ishinydex.settings \
    LANG=pt_BR.UTF-8 \
    LANGUAGE=pt_BR:en \
    LC_ALL=pt_BR.UTF-8 \
    PATH="/home/guest/.local/bin:/home/guest/.cargo/bin:$PATH" \
    PYTHONPATH="${APP_HOME}/src" \
    PYTHONUNBUFFERED=1 \
    TZ=America/Araguaina

ARG POETRY_ARGS=""
ENV POETRY_ARGS=${POETRY_ARGS}

# 2. Create User and Base Directory Structure
RUN groupadd -g 1000 guest && \
    useradd -u 1000 -g 1000 -d ${HOME} -s /bin/bash guest && \
    mkdir -p ${APP_HOME}/src/media/sprites/pokemon \
             ${APP_HOME}/src/media/sprites/types \
             ${HOME}/.jupyter && \
    chown -R 1000:1000 ${HOME}

# 3. Install OS Dependencies, Configure Locale/Timezone, and Clean Up
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive LC_ALL=C apt-get install -y --no-install-recommends \
        postgresql-client \
        python3-dev \
        zlib1g-dev \
        libpq-dev \
        gettext \
        locales \
        tzdata \
        gnupg \
        curl \
        cron \
        g++ \
        gcc \
        git && \
    if echo "$POETRY_ARGS" | grep -qE "(--with|--only| -E | --extras )dev"; then \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bash-completion; \
    fi && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    sed -i '/pt_BR.UTF-8/s/^# //g' /etc/locale.gen && locale-gen && \
    chmod u+s /usr/sbin/cron && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 4. Configure User's Bash
RUN cp /etc/skel/.bashrc ${HOME}/.bashrc && \
    chown 1000:1000 ${HOME}/.bashrc && \
    chmod 644 ${HOME}/.bashrc && \
    case "$POETRY_ARGS" in \
        *--with*dev*|*--only*dev*|*" -E "*dev*|*--extras*dev*) \
            curl -fsSL https://raw.githubusercontent.com/django/django/main/extras/django_bash_completion -o ${HOME}/.django_bash_completion && \
            printf '\n[ -f "${HOME}/.django_bash_completion" ] && source "${HOME}/.django_bash_completion"\n' >> ${HOME}/.bashrc && \
            chown 1000:1000 ${HOME}/.django_bash_completion && \
            chmod 644 ${HOME}/.django_bash_completion ;; \
        *) \
            echo "Ambiente de produção detectado. Pulando autocomplete do Django." ;; \
    esac

# 5. Copy Sprites from Builder Stage
COPY --from=sprite-builder --chown=1000:1000 /tmp/sprites/sprites/pokemon/ ${APP_HOME}/src/media/sprites/pokemon/
COPY --from=sprite-builder --chown=1000:1000 /tmp/sprites/sprites/types/ ${APP_HOME}/src/media/sprites/types/

# 6. Switch to guest user
USER guest
WORKDIR ${APP_HOME}

# 7. Install Dependencies
COPY --chown=1000:1000 pyproject.toml poetry.lock ./
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    poetry config virtualenvs.create false && \
    poetry install ${POETRY_ARGS:-} --no-interaction --no-ansi && \
    rm -rf ~/.cache/pypoetry ~/.cache/pip pyproject.toml poetry.lock

# 8. Copy Source Code
COPY --chown=1000:1000 .jupyter/ ${HOME}/.jupyter/
COPY --chown=1000:1000 src/ ${APP_HOME}/src/
COPY --chown=1000:1000 *.sh ./

WORKDIR ${APP_HOME}/src

# 9. Compile Messages and Collect Statics
RUN python manage.py compilemessages && \
    python manage.py collectstatic --clear --no-input

ENTRYPOINT ["bash", "../docker-entrypoint.sh"]
CMD ["uwsgi", "--ini", "uwsgi/ishinydex.ini"]
