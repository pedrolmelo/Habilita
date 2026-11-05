# Imagem de DESENVOLVIMENTO do frontend (Vite). Não existe imagem de produção:
# em produção o frontend são só arquivos estáticos no Firebase Hosting.
# Versão fixada por tag exata + digest (sha256).

# node:24.22.0-trixie-slim (Node 24 "Krypton", LTS ativa)
FROM node:24.22.1-trixie-slim@sha256:89c5244bc22a9bc3287d89ebc7e49b9cb5bb84cd40e6175ac3421d5a9f68b95a AS base

# Desliga o aviso "nova versão do npm disponível" (só poluía o log).
ENV NPM_CONFIG_UPDATE_NOTIFIER=false

# A imagem oficial já traz o usuário `node` (UID/GID 1000); usamos esse mesmo.
WORKDIR /app
RUN chown node:node /app
USER node

# ---------------------------------------------------------------------
# deps: instala as dependências no lockfile (npm ci = instalação congelada).
# --ignore-scripts: não roda scripts de instalação de pacotes (mais seguro).
# ---------------------------------------------------------------------
FROM base AS deps
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci --ignore-scripts

# ---------------------------------------------------------------------
# dev: servidor do Vite. node_modules fica DENTRO da imagem; o compose monta
# só src/ e public/ por volume, então nada sobrescreve node_modules.
# ---------------------------------------------------------------------
FROM deps AS dev
COPY --chown=node:node . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---------------------------------------------------------------------
# build: usado só para verificar `npm run build` dentro de um contêiner
# (`docker build --target build apps/web`). Não é publicado.
# ---------------------------------------------------------------------
FROM deps AS build
COPY --chown=node:node . .
RUN npm run build
