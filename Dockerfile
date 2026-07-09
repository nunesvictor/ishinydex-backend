FROM python:3.14-slim

# Create guest user and group
RUN groupadd -g 1000 guest && \
    useradd -u 1000 -g 1000 guest && \
    mkdir -p /home/guest && \
    chown -R 1000:1000 /home/guest && \
    cp /etc/bash.bashrc /home/guest/.bashrc

# Set current user and user's HOME env
USER guest
ENV HOME=/home/guest

# Set app's build args
ARG APP_NAME="ishinydex-backend"
ARG APP_HOME="$HOME/${APP_NAME}"
ARG POETRY_ARGS

# Set all other app envs
ENV DJANGO_SETTINGS_MODULE=ishinydex.settings
ENV LANG=pt_BR.UTF-8
ENV LANGUAGE=pt_BR:en
ENV LC_ALL=pt_BR.UTF-8
ENV PATH="$PATH:$HOME/.local/bin:$HOME/.cargo/bin"
ENV PYTHONPATH=${APP_HOME}/src
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Araguaina

# Set current workdir
RUN mkdir -p ${APP_HOME}
WORKDIR ${APP_HOME}

# Set current user
USER root

# Install build-dependencies
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
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
        git

# Copy skeleton .bashrc file to user's home
RUN awk '/shopt -oq posix/ { sub("#","",$0); print; for(n=0; n<=6; n++) { getline ; sub("#","",$0); print} }1' < /etc/bash.bashrc > /home/guest/.bashrc && \
    chown -R 1000:1000 $HOME/.bashrc && \
    chmod 644 $HOME/.bashrc

RUN case "$POETRY_ARGS" in \
        *--with*dev*|*--only*dev*|*" -E dev "*|*" --extras dev "*) \
            curl -fsSL https://raw.githubusercontent.com/django/django/main/extras/django_bash_completion -o $HOME/.django_bash_completion && \
            printf "\nsource $HOME/.django_bash_completion" >> $HOME/.bashrc && \
            DEBIAN_FRONTEND=noninteractive apt-get update && \
            DEBIAN_FRONTEND=noninteractive apt-get install -y bash-completion ;; \
    esac

# Remove apt cache
RUN rm -rf /var/lib/apt/lists/*

# Set Timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

# Set Locale
RUN sed -i '/pt_BR.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen

# Set crons bin user perms
RUN chmod u+s /usr/sbin/cron

# Download pokémon sprites
RUN git clone --filter=blob:none --no-checkout https://github.com/PokeAPI/sprites.git /tmp/sprites-repo && \
    cd /tmp/sprites-repo && \
    git sparse-checkout init --cone && \
    git sparse-checkout set sprites/pokemon sprites/types && \
    git checkout && \
    mkdir -p ${APP_HOME}/src/media/sprites/pokemon && \
    mkdir -p ${APP_HOME}/src/media/sprites/types && \
    mv sprites/pokemon/* ${APP_HOME}/src/media/sprites/pokemon/ && \
    mv sprites/types/* ${APP_HOME}/src/media/sprites/types/ && \
    chown -R 1000:1000 ${APP_HOME}/src/media/sprites && \
    rm -rf /tmp/sprites-repo

# Set current user
USER guest

# Copy poetry files to the container
COPY --chown=1000:1000 pyproject.toml poetry.lock ${APP_HOME}/

# Install poetry dependencies
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    poetry config virtualenvs.create false && \
    poetry install ${POETRY_ARGS:-} && \
    rm -rf ${APP_HOME}/pyproject.toml ${APP_HOME}/poetry.lock

# Copy jupyter files
RUN mkdir -p ${HOME}/.jupyter/
COPY --chown=1000:1000 .jupyter/* ${HOME}/.jupyter/

# Copy the rest of the application's code
COPY --chown=1000:1000 src ${APP_HOME}/src

# Set the workdir to the projects `src` folder
WORKDIR ${APP_HOME}/src

# Run collectstatic
RUN python manage.py collectstatic --clear --no-input

# Copy taks runner script
COPY --chown=1000:1000 *.sh ${APP_HOME}/

# Run entrypoint script
ENTRYPOINT ["bash", "../docker-entrypoint.sh"]

# Run uWSGI
CMD ["uwsgi", "--ini", "uwsgi/ishinydex.ini"]
