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

## Estrutura planejada do repositório

```text
apps/
  api/
    src/habilita/<modulo>/
      aplicacao/   # casos de uso (orquestram domínio e infra)
      dominio/     # regras de negócio puras (sem FastAPI, sem infra)
      infra/       # Firestore, Storage, Firebase Admin, HTTP
    tests/
      unit/  integration/  authz/  contract/  rules/  e2e/
  web/             # SPA React
seed/              # dados de demonstração e usuários com claims
infra/             # Terraform (etapa futura)
```

Hoje só existem as pastas com `README.md`. Não crie a estrutura interna antes da hora.

## Comandos

- Verificações de higiene e segredos: `pre-commit run --all-files`
- TODO(Prompt 2): subir o ambiente local (`docker compose up`) e emuladores.
- TODO(Prompt 3): lint, tipagem, testes e build da API e do web.

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
3. Rode as verificações (`pre-commit run --all-files` e, depois do Prompt 3, lint/testes) antes de concluir.
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
