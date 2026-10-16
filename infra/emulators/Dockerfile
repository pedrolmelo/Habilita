# Imagem dos emuladores do Firebase (Auth, Firestore, Storage + interface).
# Só para desenvolvimento local: nenhum recurso real do Google Cloud é usado
# (o projeto `demo-habilita` roda 100% local) e a imagem NÃO tem credenciais.
# Construir a partir da RAIZ do repositório (veja o docker-compose.yml).

# node:24.22.0-trixie-slim (Node 24 "Krypton", LTS ativa)
FROM node:26.11.1-trixie-slim@sha256:193fe51b64e77981119c98c2002c9e32a70e2f006fb4d25068ce0558998917f0

# - JRE 21 headless (sem interface gráfica): o firebase-tools 15.x exige Java 21 ou mais novo
#   para o emulador do Firestore (MIN_SUPPORTED_JAVA_MAJOR_VERSION = 21 no código dele).
#   No Debian 13 "trixie" o pacote é openjdk-21-jre-headless.
# - firebase-tools em versão exata.
# - --ignore-scripts: não roda scripts de instalação dos pacotes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global --ignore-scripts firebase-tools@15.34.0 \
    && npm cache clean --force

# - JAVA_TOOL_OPTIONS: limita a memória (heap) de CADA processo Java (Firestore e regras do
#   Storage) a 512 MiB. Sem limite, a JVM reserva uma fração grande da RAM da máquina.
# - NO_UPDATE_NOTIFIER: desliga a checagem de nova versão do CLI (sem rede inútil).
# Telemetria: o firebase-tools só envia uso se a pessoa fizer `firebase login` e aceitar;
# aqui nunca há login, então fica desligada.
ENV JAVA_TOOL_OPTIONS="-Xmx512m" \
    NO_UPDATE_NOTIFIER=1

WORKDIR /srv/firebase

# Configuração e regras (ficam na raiz do repositório, no layout padrão do Firebase).
COPY firebase.json .firebaserc firestore.rules firestore.indexes.json storage.rules ./
# Script do healthcheck: confere se as 4 portas aceitam conexão (sem instalar curl).
COPY infra/emulators/healthcheck.mjs /usr/local/bin/healthcheck.mjs

# `node` (UID/GID 1000) já existe na imagem oficial. O emulador grava logs em /srv/firebase.
RUN chown node:node /srv/firebase
USER node

# Baixa agora os executáveis dos emuladores (ficam no cache do usuário), para o contêiner
# não precisar de internet ao subir.
RUN firebase setup:emulators:firestore \
    && firebase setup:emulators:storage \
    && firebase setup:emulators:ui

# Auth 9099 | Firestore 8080 | Storage 9199 | Interface 4000
EXPOSE 9099 8080 9199 4000

# Sem --import/--export: os dados NÃO persistem entre execuções (o seed recria tudo).
CMD ["firebase", "emulators:start", "--only", "auth,firestore,storage", "--project", "demo-habilita"]
