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

> Detalhes de instalação serão acrescentados no Prompt 2.

- Git
- Docker Desktop (no Windows, com WSL2 ativado)
- Python 3.12 com [`uv`](https://docs.astral.sh/uv/)
- Node.js LTS

## Como rodar

Em breve: `docker compose up` (Prompt 2).

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
