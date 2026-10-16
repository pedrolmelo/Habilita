# AGENTS.md — Instruções para agentes de IA (e para pessoas)

Fonte única de regras para qualquer agente de IA (Antigravity, Claude Code, Codex, Copilot...) neste repositório.
Se uma ADR **aprovada** no `habilita-docs` contradisser este arquivo, a ADR vence.

## Visão do produto

- Habilita é uma plataforma B2B de conformidade documental de SST (Segurança e Saúde no Trabalho).
- Empresas contratantes controlam documentos de trabalhadores terceirizados por trabalhador e contrato.
- O sistema alerta vencimentos e mostra um semáforo (verde/amarelo/vermelho) por trabalhador.
- A portaria consulta se o trabalhador está liberado para entrar.
- Projeto acadêmico, equipe pequena com iniciantes: prefira clareza a esperteza.

## Stack (decidida; não sugira trocas)

- Web: React + TypeScript `strict` + Vite (SPA) no Firebase Hosting.
- API: Python 3.12 + FastAPI + Uvicorn, Pydantic v2, pydantic-settings, `uv`, Ruff, mypy estrito, import-linter, pytest.
- Auth: Firebase Auth com custom claims `tenantId`, `papel`, `terceirizadaId`.
- Dados: Cloud Firestore (`tenants/{tenantId}/...`), Cloud Storage privado com URL assinada.
- Execução: Cloud Run (`southamerica-east1`, `min-instances=0`) e Cloud Scheduler.
- Local: Docker Compose + Firebase Emulator Suite (Auth, Firestore, Storage).
- CI/CD: GitHub Actions com Workload Identity Federation; imagens no Artifact Registry com tag = SHA do commit.

## Estrutura do repositório

```text
.
├── apps/
│   ├── api/          # API Python 3.12 + FastAPI + Uvicorn (uv, pyproject.toml)
│   │   ├── src/habilita/
│   │   │   ├── config.py      # Configurações tipadas (pydantic-settings)
│   │   │   ├── main.py        # Fábrica FastAPI e registro de rotas
│   │   │   └── saude/rotas.py # GET /healthz (contrato OpenAPI)
│   │   └── Dockerfile         # Alvos: dev (recarga) e prod (enxuta, Cloud Run)
│   └── web/          # Frontend React + TypeScript strict + Vite SPA
│       ├── src/      # Componentes com estados explícitos (loading, success, error)
│       └── Dockerfile# Alvo dev (Vite proxy /api -> API)
├── infra/
│   ├── emulators/    # Imagem Docker dos emuladores Firebase (JRE 21 headless)
│   └── README.md     # Reservado para Terraform (etapa futura)
├── seed/             # Dados de demonstração e usuários com claims (Prompt 4)
├── docker-compose.yml# Orquestração local dos 3 serviços (127.0.0.1)
├── firebase.json     # Configuração do Firebase Emulator Suite
├── firestore.rules   # Regras deny-all do Firestore
└── storage.rules     # Regras deny-all do Cloud Storage
```

## Comandos

- Subir ambiente local completo: `docker compose up --build` (ou em segundo plano: `docker compose up -d --build`)
- Parar ambiente local: `docker compose down` (e `docker compose down -v` para limpar volumes)
- Verificações de higiene e segredos: `pre-commit run --all-files`
- Verificações da API: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports` (ou `docker compose exec api sh -c "ruff check . && ruff format --check . && mypy && lint-imports"`)
- Verificações do frontend: `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run build` (ou `docker compose exec web sh -c "npm run lint && npm run typecheck && npm run format:check && npm run build"`)
- Verificação dos Dockerfiles: `docker run --rm -v "$PWD:/repo" -w /repo hadolint/hadolint:v2.15.1-alpine hadolint apps/api/Dockerfile apps/web/Dockerfile infra/emulators/Dockerfile`
- Smoke test local do Compose: `docker compose up -d --build --wait && curl -sS -f http://127.0.0.1:8000/healthz && curl -sS -f http://127.0.0.1:5173/api/healthz && docker compose down -v`

## Convenções de Git e PR

- GitHub Flow: `main` sempre implantável e protegida; nada de push direto.
- Branch: `<tipo>/hab-<NN>-<descricao-curta>`; tipos `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.
- Commits: Conventional Commits em inglês, resumo até 72 caracteres; escopos `web`, `api`, `dominio`, `infra`, `docs`, `seed`.
- PR: um por história, ideal até ~400 linhas, título no padrão de commit, squash merge, 1 aprovação de outra pessoa.
- Preencha o modelo de PR, incluindo a seção "Uso de IA".

## Regras de ouro

### Contrato primeiro
- A fonte do contrato da API é o `openapi.yaml` (raiz do repositório `habilita-docs`).
- Mudar o contrato exige PR lá e referência a ele no PR daqui.
- As ADRs 0001 a 0004 estão "Propostas" até serem aprovadas em PR.

### Multi-tenant e autorização
- Todos os dados ficam sob `tenants/{tenantId}/...`.
- Repositórios recebem o `tenantId` no construtor, vindo da claim do token.
- **Proibido** aceitar `tenantId` ou `terceirizadaId` vindos da requisição (corpo, query, path ou header).
- Recurso de outro tenant retorna **404**; papel não permitido na rota retorna **403**.
- Security Rules são deny-all; o navegador nunca acessa o Firestore diretamente.
- Consultas `collectionGroup` só no job interno.

### Validação e dados pessoais
- Pydantic v2 com `extra="forbid"`, limites explícitos e `response_model` em toda rota.
- Erros no formato Problem Details (RFC 9457).
- Upload: PDF, JPG ou PNG até 10 MiB, tipo verificado pela assinatura de bytes (não pela extensão).
- CPF nunca em URL (consulta da portaria é POST com CPF no corpo) e armazenado como hash HMAC.
- Logs sem dados pessoais.

### Código
- `dominio/` não importa `infra/` nem FastAPI (garantido pelo import-linter).
- mypy `strict` no domínio.
- Rotas que usam `firebase-admin` são `def`, não `async def` (o SDK é bloqueante).
- Frontend em TypeScript `strict`, sem `any`, com tipos gerados do OpenAPI.
- Telas sempre com estados de carregando, vazio e erro.

### Docker e nuvem
- Imagens enxutas, usuário não-root, sem segredos em imagem ou argumento de build.
- Tag da imagem = SHA do commit; nunca `latest` em produção.
- Nenhum recurso de GCP sem ADR ou aprovação do Tech Lead.
- Até a Semana 4 (01/11) tudo roda localmente; gasto zero.

### Testes
- O nome do teste referencia o critério: `test_h03_ca2_rejeitar_sem_motivo_retorna_400`.
- Nunca apague nem desative um teste que falha para o CI passar.
- O QA é dono da estratégia de testes.

## Como trabalhar

1. Leia o código e os arquivos relacionados antes de editar.
2. Faça mudanças pequenas e focadas em uma história.
3. Rode as verificações locais (`pre-commit run --all-files`, lint da API e Web, Hadolint e build) antes de concluir.
4. Explique o que fez em português simples.
5. Pergunte quando houver ambiguidade que não dá para desfazer.
6. Não adicione dependência sem justificar no PR.
7. Sugira uma ADR (no `habilita-docs`) quando tomar uma decisão relevante.

## Nunca

- Commitar segredos ou o `.env`.
- Ler arquivos de credenciais reais (`.env`, `service-account*.json`, `*.pem`, `*.key`).
- Fazer push direto na `main` ou `git push --force`.
- Alterar proteções, rulesets ou secrets do GitHub.
- Criar recursos de nuvem.
- Desativar verificações de segurança (pre-commit, Gitleaks, CI).
