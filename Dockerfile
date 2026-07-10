FROM python:3.14-slim

# 1. Define Arguments and Environment Variables
# Kept at the top because they rarely change, preventing cache invalidation below.
ARG APP_NAME="ishinydex-backend"
ARG APP_HOME="/home/guest/${APP_NAME}"
ARG POETRY_ARGS=""

ENV HOME=/home/guest \
    DJANGO_SETTINGS_MODULE=ishinydex.settings \
    LANG=pt_BR.UTF-8 \
    LANGUAGE=pt_BR:en \
    LC_ALL=pt_BR.UTF-8 \
    PATH="/home/guest/.local/bin:/home/guest/.cargo/bin:$PATH" \
    PYTHONPATH="${APP_HOME}/src" \
    PYTHONUNBUFFERED=1 \
    TZ=America/Araguaina

# 2. Create User and Base Directory Structure
RUN groupadd -g 1000 guest && \
    useradd -u 1000 -g 1000 -d ${HOME} -s /bin/bash guest && \
    mkdir -p ${APP_HOME}/src ${HOME}/.jupyter && \
    chown -R 1000:1000 ${HOME}

# 3. Install OS Dependencies, Configure Locale/Timezone, and Clean Up
# Grouped in a single RUN to prevent the apt cache from becoming an extra layer.
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
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
        git \
        $(if echo "$POETRY_ARGS" | grep -qE "(--with|--only| -E | --extras )dev"; then echo "bash-completion"; fi) && \
    # Configure Timezone
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    # Configure Locale
    sed -i '/pt_BR.UTF-8/s/^# //g' /etc/locale.gen && locale-gen && \
    # Configure cron permissions
    chmod u+s /usr/sbin/cron && \
    # CRITICAL Clean Up: Must occur in the same layer as the installation
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 4. Configure User's Bash
RUN awk '/shopt -oq posix/ { sub("#","",$0); print; for(n=0; n<=6; n++) { getline ; sub("#","",$0); print} }1' < /etc/bash.bashrc > ${HOME}/.bashrc && \
    if echo "$POETRY_ARGS" | grep -qE "(--with|--only| -E | --extras )dev"; then \
        curl -fsSL https://raw.githubusercontent.com/django/django/main/extras/django_bash_completion -o ${HOME}/.django_bash_completion && \
        echo -e "\nsource ${HOME}/.django_bash_completion" >> ${HOME}/.bashrc; \
    fi && \
    chown 1000:1000 ${HOME}/.bashrc ${HOME}/.django_bash_completion || true && \
    chmod 644 ${HOME}/.bashrc

# 5. Download Sprites (Rarely changing layer)
# Uses a tmp folder and deletes it within the same RUN
RUN git clone --filter=blob:none --no-checkout https://github.com/PokeAPI/sprites.git /tmp/sprites && \
    cd /tmp/sprites && git sparse-checkout init --cone && \
    git sparse-checkout set sprites/pokemon sprites/types && git checkout && \
    mkdir -p ${APP_HOME}/src/media/sprites/pokemon ${APP_HOME}/src/media/sprites/types && \
    mv sprites/pokemon/* ${APP_HOME}/src/media/sprites/pokemon/ && \
    mv sprites/types/* ${APP_HOME}/src/media/sprites/types/ && \
    chown -R 1000:1000 ${APP_HOME}/src/media && \
    rm -rf /tmp/sprites

# 6. Switch to guest user
USER guest
WORKDIR ${APP_HOME}

# 7. Install Dependencies (Leveraging Cache)
# Copy ONLY poetry files first. This way, if the source code changes,
# Docker doesn't need to reinstall all Python libraries.
COPY --chown=1000:1000 pyproject.toml poetry.lock ./
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    poetry config virtualenvs.create false && \
    poetry install ${POETRY_ARGS:-} --no-interaction --no-ansi && \
    # Remove installers and deep cache for poetry/pip to save valuable MBs
    rm -rf ~/.cache/pypoetry ~/.cache/pip pyproject.toml poetry.lock

# 8. Copy Source Code (Most frequently changing layer)
COPY --chown=1000:1000 .jupyter/ ${HOME}/.jupyter/
COPY --chown=1000:1000 src/ ${APP_HOME}/src/
COPY --chown=1000:1000 *.sh ./

WORKDIR ${APP_HOME}/src

# 9. Compile Messages and Collect Statics
RUN python manage.py compilemessages && \
    python manage.py collectstatic --clear --no-input

ENTRYPOINT ["bash", "../docker-entrypoint.sh"]
CMD ["uwsgi", "--ini", "uwsgi/ishinydex.ini"]
