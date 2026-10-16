# apps/api — API do Habilita

API do Habilita desenvolvida em Python 3.12 com FastAPI, Uvicorn e Pydantic v2. Gerenciada com [`uv`](https://docs.astral.sh/uv/).

## Como rodar com Docker (recomendado)

A API sobe automaticamente junto com os outros serviços na raiz:
```bash
docker compose up -d api
```
O serviço reinicia automaticamente com recarga rápida (`--reload`) ao salvar alterações dentro de `src/`.

Verifique se a API está ativa:
```bash
curl http://localhost:8000/healthz
# Resposta esperada: {"status":"ok"}
```

Para rodar verificações de qualidade dentro do contêiner:
```bash
docker compose exec api sh -c "ruff check . && ruff format --check . && mypy && lint-imports"
```

## Como rodar sem Docker (opcional)

Pré-requisitos: Python 3.12 e `uv`.

1. Instale as dependências:
   ```bash
   uv sync
   ```

2. Se os emuladores do Firebase estiverem rodando no Docker, aponte as variáveis de ambiente locais:
   ```bash
   export FIREBASE_AUTH_EMULATOR_HOST=localhost:9099
   export FIRESTORE_EMULATOR_HOST=localhost:8080
   export FIREBASE_STORAGE_EMULATOR_HOST=localhost:9199
   ```

3. Inicie o servidor em modo de desenvolvimento:
   ```bash
   uv run uvicorn habilita.main:app --reload --port 8000
   ```

4. Verificações de lint, formatação e tipos:
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy
   uv run lint-imports
   uv run pytest
   ```
