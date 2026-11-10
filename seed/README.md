# Seed de Demonstração e Testes (Habilita)

Este diretório contém a ferramenta determinística de inicialização e população de dados de demonstração e teste para o **Habilita** contra o **Firebase Emulator Suite** (Auth, Firestore e Cloud Storage).

> [!WARNING]
> **O seed só roda contra emuladores locais.**
> O script conta com uma **trava de segurança obrigatória** que aborta a execução caso detecte credenciais reais (`GOOGLE_APPLICATION_CREDENTIALS`), hosts não-locais, ausência das variáveis de emulação ou projeto sem o prefixo obrigatório `demo-`.

---

## 1. Como Executar

### Pré-requisito: Subir o ambiente local

Suba os serviços locais (emuladores, API e Web):
```bash
docker compose up -d --build --wait
```

### Executar o seed via Docker Compose

O contêiner do seed utiliza o profile do Compose `seed` para não interferir na subida padrão do ambiente. Execute:

```bash
docker compose --profile seed run --rm seed
```

### Flags da Linha de Comando (CLI)

- `--hoje YYYY-MM-DD`: Define a data de referência para cálculo das vigências de contratos e validades de documentos de SST. Todas as datas declarativas são geradas a partir de deslocamentos em dias em relação a essa data. Padrão: `2026-10-20`.
- `--reset` / `--no-reset`: Limpa completamente o Auth, o Firestore e o bucket do Cloud Storage antes da gravação. Padrão: `--reset` (ligado).
- `--verificar`: Executa em modo somente leitura (sem nenhuma escrita). Valida contagens, regras de isolamento e integridade dos arquivos binários no Storage, imprimindo o checksum canônico do Firestore.

Exemplos:
```bash
# Execução padrão determinística com data fixa
docker compose --profile seed run --rm seed

# Apenas verificar os dados atuais sem modificar nada
docker compose --profile seed run --rm seed --verificar

# Executar com outra data de referência
docker compose --profile seed run --rm seed --hoje 2026-11-01
```

---

## 2. Usuários de Demonstração

> [!CAUTION]
> A senha listada abaixo é uma **constante exclusiva para o emulador local** e nunca deve ser usada fora dele.
> E-mails utilizam o domínio reservado `@demo.habilita.test`.

**Senha padrão do emulador:** `SenhaDemo123!`

| E-mail | UID | Papel | Tenant | Terceirizada | Finalidade |
|---|---|---|---|---|---|
| `gestor.alfa@demo.habilita.test` | `uid_gestor_alfa` | `gestor` | `tnt_alfa` | — | Gestão e aprovação de documentos de SST no Tenant Alfa |
| `porteiro.alfa@demo.habilita.test` | `uid_porteiro_alfa` | `porteiro` | `tnt_alfa` | — | Consulta de liberação na portaria no Tenant Alfa |
| `terceirizada1.alfa@demo.habilita.test` | `uid_terc_alfa_1` | `terceirizada` | `tnt_alfa` | `ter_alfa_1` | Upload e acompanhamento de trabalhadores da Terceirizada 1 |
| `terceirizada2.alfa@demo.habilita.test` | `uid_terc_alfa_2` | `terceirizada` | `tnt_alfa` | `ter_alfa_2` | Gestão de trabalhadores da Terceirizada 2 no Tenant Alfa |
| `gestor.beta@demo.habilita.test` | `uid_gestor_beta` | `gestor` | `tnt_beta` | — | Gestor do Tenant Beta (isolamento de tenant) |
| `porteiro.beta@demo.habilita.test` | `uid_porteiro_beta` | `porteiro` | `tnt_beta` | — | Portaria do Tenant Beta (testes de isolamento por CPF) |
| `terceirizada1.beta@demo.habilita.test` | `uid_terc_beta_1` | `terceirizada` | `tnt_beta` | `ter_beta_1` | Terceirizada 1 do Tenant Beta |
| `terceirizada2.beta@demo.habilita.test` | `uid_terc_beta_2` | `terceirizada` | `tnt_beta` | `ter_beta_2` | Terceirizada 2 do Tenant Beta |

As custom claims no Firebase Auth seguem rigorosamente a ADR 0002:
- `tenantId`: Identificador do tenant (`tnt_alfa` ou `tnt_beta`).
- `papel`: `gestor`, `terceirizada` ou `porteiro`.
- `terceirizadaId`: Presente **apenas** quando `papel == "terceirizada"`.

---

## 3. Cenários de Trabalhadores e Demonstração

Data de referência base $D = \text{2026-10-20}$.

### Tenant `tnt_alfa` (Contratante Alfa S.A.)

Tipos de documento exigidos: `tdoc_aso` (ASO, 12 meses) e `tdoc_nr35` (NR-35, 24 meses).

| Trabalhador | Terceirizada | Contratos Alocados | Documentos Persistidos | Semáforo Materializado | O que demonstra |
|---|---|---|---|---|---|
| `trb_alfa_1` | `ter_alfa_1` | `ctr_alfa_1`, `ctr_alfa_2` | ASO ok (D+200), NR-35 ok (D+500) | **VERDE** nos dois | **Cena de reuso (RN-08):** um único ASO atende aos dois contratos simultaneamente. |
| `trb_alfa_2` | `ter_alfa_1` | `ctr_alfa_1` | ASO ok (D+20), NR-35 ok (D+400) | **AMARELO** | Documento na faixa de 30 dias para expirar (`A_VENCER`, RN-04). |
| `trb_alfa_3` | `ter_alfa_1` | `ctr_alfa_1` | ASO vencido (D−1), NR-35 ok (D+400) | **VERMELHO** | Documento vencido bloqueia conformidade (`VENCIDO`). |
| `trb_alfa_4` | `ter_alfa_1` | `ctr_alfa_1` | ASO ok (D+200), NR-35 ausente | **VERMELHO** | Exigência contratual sem nenhum documento enviado (`AUSENTE`). |
| `trb_alfa_5` | `ter_alfa_1` | `ctr_alfa_1` | ASO ok (D+200), NR-35 PENDENTE | **VERMELHO** | Documento pendente de revisão não atende exigência contratual (RN-05). |
| `trb_alfa_6` | `ter_alfa_1` | `ctr_alfa_1` | ASO ok (D+200), NR-35 REJEITADA e NR-35 ok (D+365) | **VERDE** | **Cenário Q1:** documento rejeitado com motivo não anula documento aprovado e válido. |
| `trb_alfa_7` | `ter_alfa_1` | `ctr_alfa_4` | ASO ok (D+200) | **VERDE** (alocação) | Contrato `ctr_alfa_4` está encerrado (D−10). A portaria bloqueia entrada (RN-10). |
| `trb_alfa_8` | `ter_alfa_1` | `ctr_alfa_2` | ASO ok (D+200) | **VERDE** (alocação) | Trabalhador inativo (`ativo: false`). A portaria bloqueia entrada (RN-10). |
| `trb_alfa_y1` | `ter_alfa_2` | `ctr_alfa_3` | ASO ok (D+200) | **VERDE** | Trabalhador da Terceirizada 2 (isolamento entre terceirizadas). |

### Tenant `tnt_beta` (Espelho para Testes de Isolamento)

| Trabalhador | Terceirizada | Contratos Alocados | Documentos | Semáforo | O que demonstra |
|---|---|---|---|---|---|
| `trb_beta_1` | `ter_beta_1` | `ctr_beta_1` | ASO ok (D+200), NR-35 ok (D+400) | **VERDE** | Trabalhador válido no Tenant Beta. |
| `trb_beta_2` | `ter_beta_1` | `ctr_beta_1` | ASO vencido (D−5), NR-35 ok (D+400) | **VERMELHO** | Trabalhador bloqueado no Tenant Beta. |
| `trb_beta_y1` | `ter_beta_2` | `ctr_beta_2` | ASO ok (D+200) | **VERDE** | Trabalhador da Terceirizada 2 no Tenant Beta. |

> **Garantia de Não-Interseção:** Todos os CPFs são gerados por algoritmo com dígitos verificadores válidos, e nenhum CPF do Tenant Alfa coincide com qualquer CPF do Tenant Beta (essencial para o teste `T-ISO-04`).

---

## 4. Mapa: Cenário → Testes da Estratégia Apoiados

Os dados determinísticos fornecem base direta para os seguintes casos de teste planejados pelo QA:

| Teste | Descrição da Estratégia | Dados do Seed que Apoiam o Teste |
|---|---|---|
| **T-ISO-01** | Gestor de A acessa `/contratos/{id_B}`, `/trabalhadores/{id_B}`, etc. (esperado 404) | Recursos com IDs prefixados `ctr_beta_*`, `trb_beta_*`, `doc_beta_*`. |
| **T-ISO-02** | Gestor de A lista recursos e não enxerga nada de B | Separação das coleções em `tenants/tnt_alfa` e `tenants/tnt_beta`. |
| **T-ISO-03** | Tentativa de injeção de tenantId no payload | Contratos e trabalhadores vinculados estritamente ao tenant das claims. |
| **T-ISO-04** | Portaria de A consulta CPF existente apenas em B | CPF de `trb_beta_1` não existe no `indiceCpf` de `tnt_alfa` (retorna `NAO_CADASTRADO`). |
| **T-ISO-05** | Terceirizada 1 de A tenta acessar trabalhador da Terceirizada 2 | Usuário `uid_terc_alfa_1` vs trabalhador `trb_alfa_y1` (`ter_alfa_2`). |
| **T-ISO-06** | Acesso direto ao Firestore/Storage sem passar pela API | Prova em tempo de execução no emulador (leitura e escrita não autenticadas negadas com 403). |
| **T-ISO-07** | Gestor de A gera URL assinada para documento de B | Documentos sob prefixo estrito `tenants/tnt_beta/...`. |
| **T-ISO-08** | Requisição a rotas protegidas sem token (esperado 401 Problem Details) | Proteção global de autenticação em rotas fechadas. |
| **T-ISO-09** | Papel inadequado/RBAC (esperado 403 Problem Details) | Porteiro criando contrato ou Terceirizada aprovando documento. |
| **T-ISO-10** | IDs parecidos ou colidentes entre tenants (esperado 404) | Busca isolada por caminho `tenants/{tenantId}/...` impede match parcial. |
| **T-SEM-01** | Todos documentos VALIDO → Verde | `trb_alfa_1` em `ctr_alfa_1`. |
| **T-SEM-02** | Documentos VALIDO e A_VENCER → Amarelo | `trb_alfa_2` em `ctr_alfa_1`. |
| **T-SEM-04** | Documento VENCIDO → Vermelho | `trb_alfa_3` em `ctr_alfa_1`. |
| **T-SEM-05** | Documento ausente → Vermelho | `trb_alfa_4` em `ctr_alfa_1`. |
| **T-SEM-06** | Documento apenas PENDENTE → Vermelho | `trb_alfa_5` em `ctr_alfa_1`. |
| **T-SEM-07** | REJEITADO + outro APROVADO VALIDO → Verde | `trb_alfa_6` em `ctr_alfa_1` (Questão Q1). |
| **T-SEM-08** | Reuso de documento aprovado entre contratos | `trb_alfa_1` compartilhando `doc_alfa_1_aso` entre `ctr_alfa_1` e `ctr_alfa_2`. |
| **T-ACE-03/04**| Portaria consulta trabalhador bloqueado ou inativo | `trb_alfa_7` (contrato encerrado) e `trb_alfa_8` (inativo). |

---

## 5. Limites Conhecidos do Seed

1. **Recálculo do Semáforo no Domínio:** A lógica de cálculo do semáforo materializado reside provisoriamente em `dados.py` para alimentar o seed. Assim que o módulo de domínio e o job de recálculo forem implementados pelo Backend, a função do seed deverá ser substituída ou alinhada ao domínio para evitar risco de divergência.
2. **Dados não criados por design:** Conforme escopo do Checkpoint 1, o seed **não cria** dados de `consultasLiberacao`, `acessos`, `auditoria`, `alertas` ou `execucoesJob`. Esses dados são gerados pelas operações reais dos usuários e rotinas de sistema.
3. **Escopo local:** O seed destina-se única e exclusivamente aos emuladores locais do Firebase.
