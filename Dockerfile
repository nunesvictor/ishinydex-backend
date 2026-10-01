# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.14
ARG POETRY_VERSION=2.4.1

# ==========================================
# STAGE: sprites
# Baixa apenas os sprites efetivamente usados pela aplicação
# (ver pokedex/renderers.py, pokedex/resolvers.py e core/admin_mixins.py).
# ==========================================
FROM alpine/git:latest AS sprites

# Quantização de paleta com pngquant (mantém PNG, resolução e caminhos).
# Reduz ~70% o tamanho dos sprites HOME (512x512) com perda visual mínima.
# Use --build-arg SPRITES_OPTIMIZE=0 para manter os arquivos originais.
ARG SPRITES_OPTIMIZE=1

WORKDIR /tmp/sprites

RUN apk add --no-cache pngquant

RUN git clone --depth 1 --filter=blob:none --no-checkout \
        https://github.com/PokeAPI/sprites.git . && \
    git sparse-checkout set --no-cone \
        '/sprites/items/*.png' \
        '/sprites/pokemon/*.png' \
        '/sprites/pokemon/shiny/*.png' \
        '/sprites/pokemon/female/*.png' \
        '/sprites/pokemon/shiny/female/*.png' \
        '/sprites/pokemon/other/home/' \
        '/sprites/types/generation-viii/sword-shield/' && \
    git checkout && \
    printf '%s optimize=%s\n' "$(git rev-parse HEAD)" "$SPRITES_OPTIMIZE" \
        > sprites/.version && \
    rm -rf .git && \
    if [ "$SPRITES_OPTIMIZE" = "1" ]; then \
        find sprites -type f -name '*.png' -print0 | \
            xargs -0 -P "$(nproc)" -n 32 \
                pngquant --quality 80-95 --speed 3 --strip \
                         --skip-if-larger --force --ext .png || true; \
    fi

# ==========================================
# TARGET: sprites-data
# Imagem one-shot que popula o volume de sprites (ver serviço `sprites` no
# docker-compose.yml). Os sprites NÃO fazem parte das imagens dev/prod: ficam
# num volume Docker local, baixado uma única vez e disponível offline.
# O volume só é reescrito quando a versão (commit da PokeAPI + otimização) muda.
# ==========================================
FROM busybox:stable AS sprites-data

COPY --from=sprites /tmp/sprites/sprites/ /sprites/

COPY --chmod=755 <<'SCRIPT' /usr/local/bin/sync-sprites
#!/bin/sh
set -e
if cmp -s /sprites/.version /data/.version; then
    echo "[sprites] volume já atualizado: $(cat /data/.version)"
    exit 0
fi
echo "[sprites] populando volume: $(cat /sprites/.version)"
find /data -mindepth 1 -delete
cp -a /sprites/. /data/
echo "[sprites] concluído"
SCRIPT

CMD ["sync-sprites"]

# ==========================================
# STAGE: builder
# Toolchain de compilação (gcc, gettext, locales, poetry) que NÃO vai para a
# imagem final. Gera o virtualenv em /opt/venv.
# ==========================================
FROM python:${PYTHON_VERSION}-slim AS builder

ARG POETRY_VERSION

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
        gettext \
        locales && \
    sed -i '/pt_BR.UTF-8/s/^# //g' /etc/locale.gen && locale-gen && \
    rm -rf /var/lib/apt/lists/*

# Poetry fica isolado em seu próprio venv; o venv da aplicação não o contém.
RUN python -m venv /opt/poetry && \
    /opt/poetry/bin/pip install "poetry==${POETRY_VERSION}" && \
    python -m venv /opt/venv

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY pyproject.toml poetry.lock ./

# ------------------------------------------
# Dependências de produção
# ------------------------------------------
FROM builder AS deps-prod
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    /opt/poetry/bin/poetry install --no-root --only main,prod && \
    find /opt/venv -name '__pycache__' -prune -exec rm -rf {} +

# ------------------------------------------
# Dependências de desenvolvimento (main + prod + dev)
# ------------------------------------------
FROM builder AS deps-dev
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    /opt/poetry/bin/poetry install --no-root --with dev,prod && \
    find /opt/venv -name '__pycache__' -prune -exec rm -rf {} +

# ------------------------------------------
# Compila traduções e coleta estáticos (usa apenas as deps de produção).
# Valores fictícios satisfazem o settings.py sem expor segredos reais.
# ------------------------------------------
FROM deps-prod AS app

WORKDIR /build/src
COPY src/ ./

RUN export SECRET_KEY=build-only POSTGRES_PASSWORD=build-only && \
    python manage.py compilemessages && \
    python manage.py collectstatic --clear --no-input --verbosity 0

# ==========================================
# STAGE: base
# Runtime mínimo compartilhado por dev e prod.
# ==========================================
FROM python:${PYTHON_VERSION}-slim AS base

ARG APP_NAME="ishinydex"
ARG APP_HOME="/home/guest/${APP_NAME}"

ENV HOME=/home/guest \
    APP_HOME=${APP_HOME} \
    DJANGO_SETTINGS_MODULE=ishinydex.settings \
    LANG=pt_BR.UTF-8 \
    LANGUAGE=pt_BR:en \
    LC_ALL=pt_BR.UTF-8 \
    PATH="/opt/venv/bin:/home/guest/.local/bin:$PATH" \
    PYTHONPATH="${APP_HOME}/src" \
    PYTHONUNBUFFERED=1 \
    TZ=America/Araguaina \
    VIRTUAL_ENV=/opt/venv

# postgresql-client: pg_dump/pg_restore (backupdb/restoredb)
# cron: usado pelo docker-entrypoint.sh quando REPLICA=1
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        postgresql-client \
        tzdata \
        cron && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    chmod u+s /usr/sbin/cron && \
    groupadd -g 1000 guest && \
    useradd -u 1000 -g 1000 -d ${HOME} -s /bin/bash -m guest && \
    # src/media/sprites: ponto de montagem do volume (target sprites-data)
    mkdir -p ${APP_HOME}/src/media/sprites && chown -R 1000:1000 ${APP_HOME} && \
    rm -rf /var/lib/apt/lists/* /var/cache/debconf/*-old /var/log/*

# Apenas o locale pt_BR já compilado (evita o pacote `locales` inteiro)
COPY --from=builder /usr/lib/locale/locale-archive /usr/lib/locale/locale-archive

COPY --chown=1000:1000 docker-entrypoint.sh ${APP_HOME}/

WORKDIR ${APP_HOME}/src
ENTRYPOINT ["bash", "../docker-entrypoint.sh"]

# ==========================================
# TARGET: dev  (docker compose build → target: dev)
# ==========================================
FROM base AS dev

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        bash-completion \
        gettext && \
    rm -rf /var/lib/apt/lists/*

COPY --from=deps-dev /opt/venv /opt/venv
COPY --from=app --chown=1000:1000 /build/src/ ${APP_HOME}/src/

USER guest

ADD --chown=1000:1000 --chmod=644 \
    https://raw.githubusercontent.com/django/django/main/extras/django_bash_completion \
    ${HOME}/.django_bash_completion
RUN printf '\n[ -f "${HOME}/.django_bash_completion" ] && source "${HOME}/.django_bash_completion"\n' \
    >> ${HOME}/.bashrc

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ==========================================
# TARGET: prod  (padrão — último estágio)
# ==========================================
FROM base AS prod

COPY --from=deps-prod /opt/venv /opt/venv
COPY --from=app --chown=1000:1000 /build/src/ ${APP_HOME}/src/

USER guest

CMD ["uwsgi", "--ini", "uwsgi/ishinydex.ini"]
