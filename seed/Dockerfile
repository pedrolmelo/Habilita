# Imagem do gerador determinístico de seed do Habilita.
# Conecta exclusivamente aos emuladores locais (Auth, Firestore, Storage).
# Multi-stage build com usuário não-root (UID/GID 1000) e imagens fixadas por tag e digest.

# uv 0.13.1 (gerenciador de dependências Python)
FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv

# ---------------------------------------------------------------------
# base: Python 3.12.15 (Debian 13 "trixie") comum aos estágios
# ---------------------------------------------------------------------
FROM python:3.12.16-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS base

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
