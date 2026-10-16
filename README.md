# Habilita

Plataforma B2B de conformidade documental de Segurança e Saúde no Trabalho (SST).
Empresas que contratam terceirizados controlam documentos por trabalhador e contrato, recebem alertas de vencimento, veem um semáforo (verde/amarelo/vermelho) e consultam na portaria se o trabalhador está liberado.

## Links

- Site da documentação: https://osamuelleite.github.io/habilita-docs/
- Repositório da documentação (ADRs, contrato OpenAPI): https://github.com/osamuelleite/habilita-docs

## Estado atual

**Esqueleto do Checkpoint 1 (Fundação).** Ainda não há código de aplicação: só a estrutura de pastas, regras de contribuição e verificações automáticas de segurança.

## Estrutura de pastas

```text
.
├── apps/
│   ├── web/          # Frontend React + TypeScript + Vite (Prompt 2)
│   └── api/          # API Python 3.12 + FastAPI (Prompt 2)
├── seed/             # Dados de demonstração e usuários de teste (Prompt 4)
├── infra/            # Reservado para Terraform (etapa futura; hoje vazio)
├── .github/          # CI, modelos de PR/issues, CODEOWNERS e Dependabot
├── AGENTS.md         # Regras para agentes de IA (e um bom resumo para pessoas)
└── .env.example      # Modelo de variáveis de ambiente (copie para .env)
```

## Pré-requisitos

- **Docker e Docker Compose:**
  - **Linux:** Docker Engine + plugin Docker Compose (`docker compose version`). Adicione seu usuário ao grupo `docker` (`sudo usermod -aG docker $USER`).
  - **Windows:** Docker Desktop com backend WSL2. **Atenção:** clone o repositório dentro do sistema de arquivos do Linux no WSL (ex: `~/projects/Habilita`), **nunca** em `/mnt/c/` (para evitar lentidão drástica de I/O de disco). Recomendado limitar a memória do WSL2 criando `~/.wslconfig` no Windows com `memory=4GB`.
  - **macOS:** Docker Desktop.
- **Git**
- *(Opcional)* Python 3.12 com [`uv`](https://docs.astral.sh/uv/) e Node.js 24 LTS, caso queira executar ferramentas fora do Docker.

## Como rodar

O ambiente local sobe a API FastAPI, o frontend Vite e os emuladores do Firebase (Auth, Firestore, Storage e interface web). Funciona imediatamente em um clone limpo, sem precisar de `.env`:

```bash
# 1. Subir tudo com build das imagens:
docker compose up --build

# Ou em segundo plano (detached):
docker compose up -d --build

# 2. Ver status e saúde dos contêineres:
docker compose ps

# 3. Ver logs de um serviço específico (ex: api):
docker compose logs -f api

# 4. Parar todos os serviços:
docker compose down

# 5. Parar e limpar completamente volumes/dados efêmeros:
docker compose down -v
```

### URLs e portas locais (127.0.0.1)

Todas as portas são publicadas exclusivamente em `127.0.0.1` (loopback) para segurança:

| Serviço | URL Local | Descrição |
|---|---|---|
| **Frontend Web** | [http://localhost:5173](http://localhost:5173) | SPA React + Vite |
| **Proxy Web -> API** | [http://localhost:5173/api/healthz](http://localhost:5173/api/healthz) | Rewrite simulando Firebase Hosting |
| **API** | [http://localhost:8000](http://localhost:8000) | FastAPI / Uvicorn |
| **API Healthz** | [http://localhost:8000/healthz](http://localhost:8000/healthz) | Verificação de vida da API |
| **Emuladores UI** | [http://localhost:4000](http://localhost:4000) | Painel visual do Firebase Emulator Suite |
| **Auth Emulator** | `localhost:9099` | Emulador do Firebase Auth |
| **Firestore Emulator** | `localhost:8080` | Emulador do Cloud Firestore |
| **Storage Emulator** | `localhost:9199` | Emulador do Cloud Storage |

### Problemas comuns

- **Porta já ocupada (`port is already allocated`):**
  Copie `.env.example` para `.env` (`cp .env.example .env`) e altere a porta desejada (ex: `API_HOST_PORT=8001` ou `WEB_HOST_PORT=5174`).
- **Permissões de arquivos em volumes (Linux):**
  Os contêineres rodam com usuário comum não-root de UID/GID 1000 (`app` e `node`), compatível com o primeiro usuário padrão de distribuições Linux/Ubuntu.
- **Consumo de memória:**
  Verifique o uso de memória a qualquer momento com `docker stats --no-stream`. O consumo ocioso total de todos os serviços combinados fica em torno de ~500 MB. Os processos Java dos emuladores já possuem teto configurado com `-Xmx512m`.
- **Emuladores lentos na primeira subida:**
  Na primeira inicialização, a JVM do Firestore e Storage pode levar até ~30 segundos para carregar. O `docker-compose.yml` já conta com `start_period` tolerante nos healthchecks.
- **Como reconstruir imagens após alterar dependências:**
  Se alterar `pyproject.toml`, `uv.lock`, `package.json` ou `package-lock.json`, reconstrua os contêineres com:
  ```bash
  docker compose up --build
  ```

## Integração Contínua (CI)

O repositório possui pipeline automatizado no GitHub Actions executado a cada Pull Request e push na branch `main`:

| Job | O que verifica | Como rodar localmente |
|---|---|---|
| `segredos` | Varrer todo o histórico Git com Gitleaks à procura de credenciais e segredos vazados | `pre-commit run gitleaks --all-files` |
| `higiene` | Formatação de arquivos, quebras de linha LF, sintaxe YAML/JSON e arquivos grandes | `pre-commit run --all-files` |
| `api-qualidade` | Linting (`ruff check .`), formatação (`ruff format --check .`), tipagem estrita (`mypy`) e isolamento arquitetural (`lint-imports`) na API Python | `cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports`<br>*(ou via contêiner: `docker compose exec api sh -c "ruff check . && ruff format --check . && mypy && lint-imports"`)* |
| `web-qualidade` | Linting (`eslint .`), tipagem estrita (`tsc`) e formatação (`prettier --check .`) no frontend React | `cd apps/web && npm run lint && npm run typecheck && npm run format:check`<br>*(ou via contêiner: `docker compose exec web sh -c "npm run lint && npm run typecheck && npm run format:check"`)* |
| `web-build` | Compilação estática do frontend de produção via Vite (`npm run build`), bloqueada se o lint falhar | `cd apps/web && npm run build`<br>*(ou via contêiner: `docker compose exec web npm run build`)* |
| `dockerfiles` | Conformidade, boas práticas e segurança dos Dockerfiles com Hadolint | `docker run --rm -v "$PWD:/repo" -w /repo hadolint/hadolint:v2.15.1-alpine hadolint apps/api/Dockerfile apps/web/Dockerfile infra/emulators/Dockerfile` |
| `compose-smoke` | Subida real do ambiente do zero sem `.env` (`docker compose up -d --build --wait`), validação dos endpoints `/healthz`, proxy Vite e regra deny-all do Firestore | `docker compose config`<br>`docker compose up -d --build --wait`<br>`curl -sS -f http://127.0.0.1:8000/healthz`<br>`curl -sS -f http://127.0.0.1:5173/api/healthz`<br>`docker compose down -v` |
| `ci-ok` | Check agregador estável: consolida todos os jobs e falha se qualquer um falhar, for cancelado ou pulado (único check obrigatório na proteção da `main`) | Avaliado automaticamente no GitHub Actions |

## Como contribuir

Resumo (detalhes em [Como contribuir](https://osamuelleite.github.io/habilita-docs/engenharia/contribuir/)):

1. Usamos **GitHub Flow**: a `main` está sempre implantável e protegida. Ninguém faz push direto nela.
2. Cada história vira uma branch curta: `<tipo>/hab-<NN>-<descricao-curta>`, com `tipo` = `feat`, `fix`, `docs`, `test`, `chore` ou `refactor`. Exemplo: `feat/hab-03-rejeitar-documento`.
3. Commits em **Conventional Commits**, em inglês, até 72 caracteres no resumo. Escopos: `web`, `api`, `dominio`, `infra`, `docs`, `seed`. Exemplo: `feat(api): reject document without reason`.
4. Um **Pull Request** por história (ideal até ~400 linhas), título no padrão de commit, 1 aprovação de outra pessoa, CI verde e merge por squash.
5. Preencha o checklist da Definition of Done no modelo de PR.

## Segurança

- **Nunca** commite o arquivo `.env`, chaves, tokens ou arquivos de credenciais (`service-account*.json`, `*.pem`, `*.key`). Use o `.env.example` como modelo.
- Ative o **pre-commit** (ferramenta que roda verificações antes de cada commit, inclusive a busca de segredos com Gitleaks):

  ```bash
  pip install pre-commit        # ou: uv tool install pre-commit
  pre-commit install            # ativa no seu clone (uma vez só)
  pre-commit run --all-files    # roda tudo manualmente
  ```

- Se um segredo for commitado por engano, avise o DevOps/Tech Lead imediatamente: o segredo deve ser **revogado**, não basta apagar o arquivo.
