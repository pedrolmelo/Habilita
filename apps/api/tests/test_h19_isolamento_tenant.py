"""Testes de isolamento multi-tenant (História H19 / Requisito RNF01).

Especificação:
- História: H19 (Isolar dados por cliente e papel)
- Requisito Não Funcional: RNF01 (Autorização por cliente e papel em 100% das rotas)
- ADR Relacionada: ADR 0002 (Multi-tenant e autorização)
- Casos de Teste da Estratégia de QA: T-ISO-01 a T-ISO-07
- Referência: docs/testes/estrategia.md (Seção 5) e seed/README.md (Seção 4)

Nota para o Checkpoint 1 (18/10/2026):
Conforme definido no Guia do PO (Checkpoint 1) e na ADR 0002:
"Teste de isolamento de tenant escrito (nos projetos com várias empresas clientes).
Ele verifica que um usuário da empresa A recebe erro 403 ou 404 ao acessar dados da
empresa B. O teste pode falhar agora, porque o sistema ainda não existe, mas ele
precisa estar escrito."
Endpoints previstos para implementação completa na Semana 4 (01/11/2026).
"""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from .conftest import (
    CPF_TRB_BETA_1,
    CTR_BETA_1,
    DOC_BETA_1_ASO,
    TER_ALFA_1,
    TNT_ALFA,
    TNT_BETA,
    TRB_ALFA_Y1,
    TRB_BETA_1,
)


def test_h19_ca1_t_iso_01_gestor_acessa_recursos_outro_tenant_retorna_404(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """T-ISO-01 (H19.CA1): Gestor de A acessa recursos do Tenant B por ID.

    Dado:
        Um usuário autenticado como Gestor SST do Tenant Alfa (tnt_alfa).
    Quando:
        O gestor tenta obter recursos pertencentes exclusivamente ao Tenant Beta (tnt_beta):
        - GET /contratos/{id_B}
        - GET /trabalhadores/{id_B}
        - GET /documentos/{id_B}
    Então:
        A API responde HTTP 404 em todos os endpoints, com payload Problem Details (RFC 9457)
        oriundo da camada de autorização/guard de tenant, sem expor que o recurso existe
        nem vazar nenhum dado de negócio do Tenant Beta no corpo da resposta.
    """
    recursos_beta = [
        f"/contratos/{CTR_BETA_1}",
        f"/trabalhadores/{TRB_BETA_1}",
        f"/documentos/{DOC_BETA_1_ASO}",
    ]

    for rota in recursos_beta:
        resposta = client.get(rota, headers=headers_gestor_alfa)

        assert resposta.status_code == 404, (
            f"Esperado HTTP 404 ao acessar recurso de outro tenant em {rota}, "
            f"mas obteve HTTP {resposta.status_code}."
        )

        # Valida que o 404 vem da camada de autorização (formato problem+json da RFC 9457/7807)
        # e não um 404 genérico de rota inexistente do FastAPI
        assert "application/problem+json" in resposta.headers.get("content-type", ""), (
            f"Esperado header Content-Type 'application/problem+json' em {rota}, "
            f"mas obteve '{resposta.headers.get('content-type')}'."
        )
        corpo_json = resposta.json()
        assert corpo_json.get("status") == 404, (
            f"Esperado campo 'status': 404 no corpo problem+json em {rota}, "
            f"mas obteve {corpo_json.get('status')}."
        )
        assert "title" in corpo_json or "type" in corpo_json, (
            f"Corpo da resposta em {rota} não segue o contrato Problem Details: {corpo_json}"
        )

        corpo_texto = resposta.text.lower()
        # Não pode conter identificadores confidenciais do tenant B
        assert TNT_BETA not in corpo_texto, f"Vazamento de tenantId de B em {rota}!"
        assert "beta" not in corpo_texto or "detail" in corpo_texto, (
            f"Vazamento de dados do recurso de B no corpo da resposta em {rota}."
        )


@pytest.mark.xfail(
    strict=False,
    reason="Endpoints de listagem (H01, H02, H19) previstos para implementação na Semana 4.",
)
def test_h19_ca1_t_iso_02_gestor_lista_recursos_nao_enxerga_outro_tenant(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """T-ISO-02 (H19.CA1): Gestor de A lista recursos e não enxerga nada de B.

    Dado:
        Um usuário autenticado como Gestor SST do Tenant Alfa (tnt_alfa).
    Quando:
        O gestor lista contratos, trabalhadores, documentos, alertas e auditoria.
    Então:
        A API responde HTTP 200 contendo apenas itens pertencentes ao Tenant Alfa.
        Nenhum item pertencente ao Tenant Beta pode ser retornado na listagem.
    """
    rotas_listagem = [
        "/contratos",
        "/trabalhadores",
        "/documentos",
        "/alertas",
        "/auditoria",
    ]

    for rota in rotas_listagem:
        resposta = client.get(rota, headers=headers_gestor_alfa)
        assert resposta.status_code == 200, f"Falha ao listar {rota}: status {resposta.status_code}"

        dados: dict[str, Any] = resposta.json()
        itens: list[dict[str, Any]] = dados.get("itens", [])

        # Garante que nenhum item de Beta está presente
        for item in itens:
            item_str = str(item).lower()
            assert "beta" not in item_str, f"Recurso do Tenant Beta vazou na listagem de {rota}!"
            assert item.get("tenantId", TNT_ALFA) == TNT_ALFA


def test_h19_ca5_t_iso_03_injecao_tenant_id_criacao_contrato_isolado_no_tenant_da_claim(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """T-ISO-03 (H19.CA5): Tentativa de injeção de tenantId no payload/query/header.

    Dado:
        Um usuário autenticado do Tenant Alfa (tnt_alfa).
    Quando:
        O usuário tenta criar um contrato enviando tenantId="tnt_beta" no corpo JSON,
        na query string (?tenantId=tnt_beta) e no header (X-Tenant-Id: tnt_beta).
    Então:
        Conforme a ADR 0002 e AGENTS.md, é terminantemente PROIBIDO aceitar tenantId
        da requisição. A API deve rejeitar o campo extra (400/422) ou ignorá-lo e
        persistir o recurso exclusivamente no tenant da claim (tnt_alfa).
        Nenhum dado pode ser criado ou modificado no Tenant Beta.
    """
    payload_com_injecao = {
        "identificador": "CTR-TEST-INJECTION-01",
        "terceirizadaId": TER_ALFA_1,
        "tenantId": TNT_BETA,  # Tentativa de injeção direta no payload
    }

    headers_com_injecao = {
        **headers_gestor_alfa,
        "X-Tenant-Id": TNT_BETA,  # Tentativa de injeção via header
    }

    resposta = client.post(
        "/contratos?tenantId=tnt_beta",  # Tentativa de injeção via query parameter
        json=payload_com_injecao,
        headers=headers_com_injecao,
    )

    # Aceita 400/422 se o schema Pydantic com extra="forbid" rejeitar o tenantId no payload
    # OU 201 se o endpoint criou o recurso ignorando o parâmetro e usando o tenant da claim
    assert resposta.status_code in (201, 400, 422), (
        f"Código inesperado na tentativa de injeção: {resposta.status_code}"
    )

    if resposta.status_code == 201:
        contrato_criado: dict[str, Any] = resposta.json()
        assert contrato_criado.get("tenantId") != TNT_BETA, (
            "VULNERABILIDADE CRÍTICA: Contrato criado no tenant injetado (tnt_beta)!"
        )
        assert contrato_criado.get("tenantId", TNT_ALFA) == TNT_ALFA


@pytest.mark.xfail(
    strict=False,
    reason="Rota POST /liberacoes/consultas prevista para implementação na Semana 4 (ADR 0008).",
)
def test_h19_ca1_t_iso_04_portaria_consulta_cpf_outro_tenant_retorna_nao_cadastrado(
    client: TestClient,
    headers_porteiro_alfa: dict[str, str],
) -> None:
    """T-ISO-04 (H19.CA1): Portaria de A consulta CPF que só existe no Tenant B.

    Dado:
        Um porteiro do Tenant Alfa consultando liberação de acesso na portaria.
    Quando:
        Consulta via POST /liberacoes/consultas um CPF que está cadastrado apenas
        no Tenant Beta (trb_beta_1).
    Então:
        A consulta responde 200 com resultado="NAO_CADASTRADO".
        Nenhum dado pessoal do trabalhador do Tenant Beta (nome, empresa, contratos)
        pode ser revelado ao porteiro do Tenant Alfa.
    """
    payload_consulta = {
        "cpf": CPF_TRB_BETA_1,  # CPF pertencente a Alexandre Pires Barbosa (tnt_beta)
    }

    resposta = client.post(
        "/liberacoes/consultas",
        json=payload_consulta,
        headers=headers_porteiro_alfa,
    )

    assert resposta.status_code == 200, (
        f"Esperado HTTP 200 na consulta da portaria, obtido {resposta.status_code}"
    )

    resultado: dict[str, Any] = resposta.json()
    assert resultado.get("resultado") == "NAO_CADASTRADO", (
        f"Esperado 'NAO_CADASTRADO', mas obteve '{resultado.get('resultado')}'"
    )

    # Valida que não houve vazamento de dados do trabalhador de B
    assert "trabalhador" not in resultado or resultado.get("trabalhador") is None
    assert resultado.get("contratosAptos") == []
    assert "Alexandre Pires Barbosa" not in resposta.text


def test_h19_ca3_t_iso_05_terceirizada_acessa_trabalhador_outra_terceirizada_retorna_404(
    client: TestClient,
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """T-ISO-05 (H19.CA3): Terceirizada 1 de A tenta acessar trabalhador da Terceirizada 2.

    Dado:
        Usuário com papel 'terceirizada' vinculado à Terceirizada 1 (ter_alfa_1).
    Quando:
        Faz GET em /trabalhadores/{trb_alfa_y1}, que pertence à Terceirizada 2 (ter_alfa_2).
    Então:
        A API responde HTTP 404 (isolamento horizontal intra-tenant entre terceirizadas),
        com formato Problem Details (RFC 9457, application/problem+json).
    """
    rota = f"/trabalhadores/{TRB_ALFA_Y1}"
    resposta = client.get(rota, headers=headers_terceirizada_1_alfa)

    assert resposta.status_code == 404, (
        f"Esperado HTTP 404 no acesso entre terceirizadas distintas em {rota}, "
        f"mas obteve HTTP {resposta.status_code}."
    )
    assert "application/problem+json" in resposta.headers.get("content-type", ""), (
        f"Esperado header Content-Type 'application/problem+json' em {rota}, "
        f"mas obteve '{resposta.headers.get('content-type')}'."
    )
    corpo_json = resposta.json()
    assert corpo_json.get("status") == 404, (
        f"Esperado campo 'status': 404 no corpo problem+json em {rota}, "
        f"mas obteve {corpo_json.get('status')}."
    )
    assert "title" in corpo_json or "type" in corpo_json, (
        f"Corpo da resposta em {rota} não segue o contrato Problem Details: {corpo_json}"
    )


def test_h19_ca4_t_iso_06_acesso_direto_firestore_storage_sem_api_rejeitado_deny_all() -> None:
    """T-ISO-06 (H19.CA4): Regras deny-all bloqueiam acesso direto ao Firestore e Storage.

    Dado:
        O navegador ou cliente Firebase tentando ler ou escrever diretamente
        no Firestore ou Cloud Storage sem passar pela API FastAPI.
    Quando:
        As Security Rules são avaliadas.
    Então:
        Tanto firestore.rules quanto storage.rules contêm a regra estrita deny-all
        'allow read, write: if false;', impedindo qualquer bypass da camada de autorização.
    """
    caminhos_busca: list[Path] = [
        Path("/app"),
        Path.cwd(),
    ]
    parents = Path(__file__).resolve().parents
    if len(parents) > 3:
        caminhos_busca.insert(0, parents[3])

    arquivo_firestore_rules = next(
        (p / "firestore.rules" for p in caminhos_busca if (p / "firestore.rules").is_file()),
        Path("firestore.rules"),
    )
    arquivo_storage_rules = next(
        (p / "storage.rules" for p in caminhos_busca if (p / "storage.rules").is_file()),
        Path("storage.rules"),
    )

    assert arquivo_firestore_rules.is_file(), (
        f"Arquivo firestore.rules não encontrado em {arquivo_firestore_rules}"
    )
    assert arquivo_storage_rules.is_file(), (
        f"Arquivo storage.rules não encontrado em {arquivo_storage_rules}"
    )

    conteudo_firestore = arquivo_firestore_rules.read_text(encoding="utf-8")
    conteudo_storage = arquivo_storage_rules.read_text(encoding="utf-8")

    # Verifica que a diretiva deny-all está explicitamente presente
    assert "allow read, write: if false;" in conteudo_firestore, (
        "firestore.rules deve conter 'allow read, write: if false;'"
    )
    assert "allow read, write: if false;" in conteudo_storage, (
        "storage.rules deve conter 'allow read, write: if false;'"
    )


def test_h19_ca1_t_iso_07_gestor_gera_url_download_documento_outro_tenant_retorna_404(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """T-ISO-07 (H19.CA1): Gestor de A tenta gerar URL assinada para documento de B.

    Dado:
        Um usuário Gestor SST do Tenant Alfa.
    Quando:
        Tenta gerar link temporário de download (POST /documentos/{id_B}/url-download)
        para um documento armazenado sob o escopo do Tenant Beta (doc_beta_1_aso).
    Então:
        A API responde HTTP 404, bloqueando a geração de URL assinada para outro tenant,
        com formato Problem Details (RFC 9457, application/problem+json).
    """
    rota = f"/documentos/{DOC_BETA_1_ASO}/url-download"
    resposta = client.post(rota, headers=headers_gestor_alfa)

    assert resposta.status_code == 404, (
        f"Esperado HTTP 404 ao solicitar URL de documento de outro tenant em {rota}, "
        f"mas obteve HTTP {resposta.status_code}."
    )
    assert "application/problem+json" in resposta.headers.get("content-type", ""), (
        f"Esperado header Content-Type 'application/problem+json' em {rota}, "
        f"mas obteve '{resposta.headers.get('content-type')}'."
    )
    corpo_json = resposta.json()
    assert corpo_json.get("status") == 404, (
        f"Esperado campo 'status': 404 no corpo problem+json em {rota}, "
        f"mas obteve {corpo_json.get('status')}."
    )
    assert "title" in corpo_json or "type" in corpo_json, (
        f"Corpo da resposta em {rota} não segue o contrato Problem Details: {corpo_json}"
    )
