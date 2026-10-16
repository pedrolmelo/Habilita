## O que muda e por quê

<!-- Descreva em poucas linhas o que este PR faz e qual problema resolve. -->

## História e critérios de aceite

- História: <!-- ex.: H03 -->
- Critérios atendidos: <!-- ex.: H03.CA1, H03.CA2 -->
- Issue: <!-- ex.: Closes #12 -->

## Como testar

<!-- Passo a passo para quem revisa reproduzir. -->
1.
2.

## Checklist da Definition of Done

- [ ] PR revisado por outra pessoa (diferente do autor) e CI verde
- [ ] Teste novo ligado a um critério de aceite (ex.: `test_h03_ca2_...`)
- [ ] Nenhum segredo no código (tokens, chaves, `.env`, credenciais)
- [ ] Telas com estados de carregando, vazio e erro (se houver tela)
- [ ] Logs sem dados pessoais
- [ ] Nenhum recurso novo no GCP sem ADR ou aprovação do Tech Lead
- [ ] Docs/OpenAPI atualizados no repositório `habilita-docs` quando o contrato ou uma decisão mudou (link do PR lá: )

## Segurança

- [ ] Sem segredos no código nem no histórico de commits
- [ ] Sem dados pessoais (CPF, nome, e-mail etc.) em logs, URLs ou prints
- [ ] `tenantId` (e `terceirizadaId`) vêm sempre da claim do token, **nunca** da requisição

## Uso de IA

- Usou alguma ferramenta de IA? <!-- sim / não -->
- Qual? <!-- ex.: Antigravity, Claude Code, Copilot -->
- O que foi revisado por uma pessoa? <!-- ex.: revisei toda a lógica de autorização e os testes -->

## Evidências

<!-- Prints ou logs SEM dados pessoais. -->
