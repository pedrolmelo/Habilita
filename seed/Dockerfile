# Imagem do gerador determinístico de seed do Habilita.
# Conecta exclusivamente aos emuladores locais (Auth, Firestore, Storage).
# Multi-stage build com usuário não-root (UID/GID 1000) e imagens fixadas por tag e digest.

# uv 0.13.1 (gerenciador de dependências Python)
FROM ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 AS uv

# ---------------------------------------------------------------------
# base: Python 3.12.15 (Debian 13 "trixie") comum aos estágios
# ---------------------------------------------------------------------
FROM python:3.12.15-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Usuário comum (UID/GID 1000): processo nunca roda como root
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

# ---------------------------------------------------------------------
# build: instala dependências de produção sem dev tools
# ---------------------------------------------------------------------
FROM base AS build
COPY --from=uv /uv /bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY README.md pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------------
# runner: imagem final enxuta, sem compiladores ou ferramentas extras
# ---------------------------------------------------------------------
FROM base AS runner
COPY --from=build /opt/venv /opt/venv
USER 1000:1000
ENTRYPOINT ["python", "-m", "habilita_seed"]
