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
- Auth: Firebase Auth com custom claims `tenantId`, `papel` (`admin_contratante` | `analista_sst` | `terceirizada` | `porteiro`, ADR 0002) e `terceirizadaId`.
- Dados: Cloud Firestore no plano Spark (`tenants/{tenantId}/...`, local `us-central1`) e **Supabase Storage** (plano gratuito) em bucket privado, com URL assinada curta gerada pela API (ADR 0006).
- Execução: API no **Render** (web service gratuito, mesmo `Dockerfile`), job diário no **GitHub Actions** (`schedule`) chamando a rota interna com `JOB_TOKEN` (ADR 0007) e monitoramento no **UptimeRobot** (`/readyz`).
- Local: Docker Compose + Firebase Emulator Suite (Auth e Firestore) + Supabase Storage local.
- CI/CD: GitHub Actions (`ci-ok`); deploy da API pelo Render no merge da `main` depois do CI verde; frontend no Firebase Hosting com preview por PR.

## Plano Custo Zero (ADR 0010 do `habilita-docs`, definido pelo monitor)

- **Nunca** cadastrar cartão nem conta de faturamento em nenhum serviço (Google Cloud, Firebase, Render, Supabase, GitHub).
- **Nunca** ativar o plano Blaze do Firebase nem usar serviços pagos do GCP (Cloud Run, Cloud Storage, Cloud Scheduler, Secret Manager, Artifact Registry, Workload Identity Federation).
- Segredos (chave da conta de serviço do Firebase Admin, `SUPABASE_SERVICE_KEY`, `JOB_TOKEN`, chave HMAC do CPF) ficam **só** em secrets do GitHub e variáveis do Render. No código, segredo obrigatório **não tem valor padrão**: a API não sobe sem ele.
- Testes pesados, carga (k6) e seed grande **só** no Compose local, nunca contra o Firestore real (cota diária do Spark).
- Na dúvida, não ative: serviço novo só com ADR e aprovação do Tech Lead.

## Estrutura do repositório

```text
.
├── apps/
│   ├── api/          # API Python 3.12 + FastAPI + Uvicorn (uv, pyproject.toml)
│   │   ├── src/habilita/
│   │   │   ├── config.py      # Configurações tipadas (pydantic-settings)
│   │   │   ├── main.py        # Fábrica FastAPI e registro de rotas
│   │   │   └── saude/rotas.py # GET /healthz (contrato OpenAPI)
│   │   └── Dockerfile         # Alvos: dev (recarga) e prod (enxuta, Render)
│   └── web/          # Frontend React + TypeScript strict + Vite SPA
│       ├── src/      # Componentes com estados explícitos (loading, success, error)
│       └── Dockerfile# Alvo dev (Vite proxy /api -> API)
├── infra/
│   ├── emulators/    # Imagem Docker dos emuladores Firebase (Auth e Firestore)
│   └── README.md     # Reservado para Terraform (etapa futura)
├── seed/             # Dados de demonstração e usuários com claims (Prompt 4)
├── docker-compose.yml# Orquestração local (127.0.0.1): web, API, emuladores e Supabase Storage
├── firebase.json     # Configuração do Firebase Emulator Suite
├── firestore.rules   # Regras deny-all do Firestore
└── storage.rules     # Regras deny-all do Cloud Storage (mantidas para o caso de voltar ao GCP)
```

## Comandos

- Subir ambiente local completo: `docker compose up --build` (ou em segundo plano: `docker compose up -d --build`)
- Parar ambiente local: `docker compose down` (e `docker compose down -v` para limpar volumes)
- Executar seed de demonstração: `docker compose --profile seed run --rm seed` (modo verificação: `docker compose --profile seed run --rm seed --verificar`)
- Verificações de higiene e segredos: `pre-commit run --all-files`
- Verificações da API: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports` (ou `docker compose exec api sh -c "ruff check . && ruff format --check . && mypy && lint-imports"`)
- Verificações do seed: `cd seed && uv run ruff check . && uv run ruff format --check . && uv run mypy`
- Verificações do frontend: `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run build` (ou `docker compose exec web sh -c "npm run lint && npm run typecheck && npm run format:check && npm run build"`)
- Verificação dos Dockerfiles: `docker run --rm -v "$PWD:/repo" -w /repo hadolint/hadolint:v2.15.1-alpine hadolint apps/api/Dockerfile apps/web/Dockerfile infra/emulators/Dockerfile seed/Dockerfile`
- Smoke test local do Compose: `docker compose up -d --build --wait && curl -sS -f http://127.0.0.1:8000/healthz && curl -sS -f http://127.0.0.1:5173/api/healthz && docker compose --profile seed run --rm seed && docker compose down -v`

## Convenções de Git e PR

- GitHub Flow: `main` sempre implantável e protegida; nada de push direto.
- Branch: `<tipo>/hab-<NN>-<descricao-curta>`; tipos `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.
- Commits: Conventional Commits em inglês, resumo até 72 caracteres; escopos `web`, `api`, `dominio`, `infra`, `docs`, `seed`.
- PR: um por história, ideal até ~400 linhas, título no padrão de commit, squash merge, **2 aprovações** de outras pessoas (incluindo um dono do CODEOWNERS).
- Preencha o modelo de PR, incluindo a seção "Uso de IA".

## Regras de ouro

### Contrato primeiro
- A fonte do contrato da API é o `openapi.yaml` (raiz do repositório `habilita-docs`).
- Mudar o contrato exige PR lá e referência a ele no PR daqui.
- As ADRs 0001 a 0004 são aprovadas em PR no `habilita-docs`; confira o status no índice de ADRs antes de contrariar uma decisão.
- Valor diferente do Caderno, da ficha ou do Plano Custo Zero só com linha na ADR 0011 (divergências e interpretações).

### Multi-tenant e autorização
- Todos os dados ficam sob `tenants/{tenantId}/...`.
- Repositórios recebem o `tenantId` no construtor, vindo da claim do token.
- **Proibido** aceitar `tenantId` ou `terceirizadaId` vindos da requisição (corpo, query, path ou header).
- Recurso de outro tenant retorna **404**; papel não permitido na rota retorna **403**.
- Só `admin_contratante` cria contratos e edita a matriz de exigências; `analista_sst` aprova ou rejeita documentos e **não** edita a matriz.
- Security Rules do Firestore são deny-all; o bucket do Supabase não tem política para `anon`/`authenticated`; o navegador nunca acessa Firestore nem Storage diretamente e nunca recebe chave do Supabase.
- Consultas `collectionGroup` só no job interno.

### Validação e dados pessoais
- Pydantic v2 com `extra="forbid"`, limites explícitos e `response_model` em toda rota.
- Erros no formato Problem Details (RFC 9457).
- Upload **multipart pela API**: **PDF ou JPG até 5 MB (5.000.000 bytes)**; 5.000.001 → 413; outro tipo → 415; tipo verificado pela assinatura de bytes (não pela extensão); imagens comprimidas no cliente (máx. 2000 px, JPEG 0,8) e miniatura de JPG gerada na API. Download por URL assinada de 300 s. Expurgo 90 dias depois de o arquivo deixar de ser necessário, feito pelo job diário (ADR 0006).
- Portaria: a resposta da consulta nunca traz dado de documento (tipo, motivo, validade, semáforo ou contrato), só o resultado e uma orientação genérica (ADR 0008).
- CPF nunca em URL (consulta da portaria é POST com CPF no corpo) e armazenado como hash HMAC.
- Logs sem dados pessoais.
- CORS: allowlist explícita (domínio `.web.app`/`.firebaseapp.com` do projeto e `localhost:5173`), nunca `*`, sem `allow_credentials` (ADR 0010).
- Autenticação só por Firebase ID token verificado. **Proibido** qualquer atalho de autenticação (token simulado, cabeçalho `X-Simulated-*`) no código da aplicação; nos testes, use `app.dependency_overrides`.

### Código
- `dominio/` não importa `infra/` nem FastAPI (garantido pelo import-linter).
- mypy `strict` no domínio.
- Rotas que usam `firebase-admin` são `def`, não `async def` (o SDK é bloqueante).
- Frontend em TypeScript `strict`, sem `any`, com tipos gerados do OpenAPI.
- Telas sempre com estados de carregando, vazio e erro.

### Docker e nuvem
- Imagens enxutas, usuário não-root, sem segredos em imagem ou argumento de build.
- Tag da imagem = SHA do commit; nunca `latest` em produção.
- Nenhum recurso novo em nuvem sem ADR ou aprovação do Tech Lead.
- Gasto sempre US$ 0,00 (Plano Custo Zero); a partir da Semana 5, publicação em Hosting + Render + Supabase.
- O seed só roda contra serviços locais (emuladores de Auth e Firestore e Supabase Storage local); aborta obrigatoriamente se detectar credenciais reais ou hosts não-locais.

### Testes
- O nome do teste referencia o critério: `test_h03_ca2_rejeitar_sem_motivo_retorna_400`.
- Nunca apague nem desative um teste que falha para o CI passar; `pytest.skip` por falta de serviço local não vale como teste passando no CI.
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
- Criar recursos de nuvem, usar serviço pago, ativar o Blaze ou cadastrar cartão.
- Desativar verificações de segurança (pre-commit, Gitleaks, CI). Allowlist do Gitleaks só por regra e trecho específicos, com comentário do motivo; nunca um arquivo inteiro.
