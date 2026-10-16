# Imagem da API do Habilita. Dois alvos (`--target`):
#   dev  -> recarrega sozinha ao editar o código (usada no docker compose)
#   prod -> enxuta, sem ferramentas de desenvolvimento (será usada no Cloud Run)
# Versões fixadas por tag exata + digest (sha256) para o build ser reproduzível.

# uv 0.13.1 (gerenciador de dependências Python)
FROM ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 AS uv

# ---------------------------------------------------------------------
# base: Python 3.12.15 (Debian 13 "trixie") comum a todos os estágios
# ---------------------------------------------------------------------
# python:3.12.15-slim
FROM python:3.14.8-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS base

# - sem .pyc (menos lixo) e logs sem buffer (aparecem na hora no `docker logs`)
# - PORT: porta da API (o Cloud Run também injeta PORT); padrão 8000
# - /opt/venv: ambiente virtual com as dependências, fora de /app para o volume não sobrescrevê-lo
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PATH="/opt/venv/bin:$PATH"

# Usuário comum (UID/GID 1000): o processo nunca roda como root.
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
EXPOSE 8000

# Sem curl na imagem: o healthcheck usa o próprio Python.
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/healthz', timeout=3)"]

# ---------------------------------------------------------------------
# build-prod: instala só as dependências de execução (sem grupo dev)
# ---------------------------------------------------------------------
FROM base AS build-prod
COPY --from=uv /uv /bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
# `--frozen`: usa o uv.lock exatamente como está (falha se estiver desatualizado).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------------
# build-dev: dependências de execução + ferramentas de desenvolvimento
# ---------------------------------------------------------------------
FROM base AS build-dev
COPY --from=uv /uv /bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# ---------------------------------------------------------------------
# dev: recarga automática. O código vem de um volume montado em /app/src.
# ---------------------------------------------------------------------
FROM base AS dev
COPY --from=build-dev /opt/venv /opt/venv
COPY pyproject.toml ./
COPY src ./src
# /app gravável pelo usuário comum: ruff, mypy e pytest criam pastas de cache aqui.
RUN chown 1000:1000 /app
USER 1000:1000
# `sh -c` só para expandir ${PORT}; `exec` faz o Uvicorn receber os sinais de parada.
CMD ["sh", "-c", "exec uvicorn habilita.main:app --reload --reload-dir /app/src --host 0.0.0.0 --port \"${PORT}\""]

# ---------------------------------------------------------------------
# prod: sem recarga, sem ferramentas de desenvolvimento, usuário não-root
# ---------------------------------------------------------------------
FROM base AS prod
COPY --from=build-prod /opt/venv /opt/venv
USER 1000:1000
CMD ["python", "-m", "habilita"]
