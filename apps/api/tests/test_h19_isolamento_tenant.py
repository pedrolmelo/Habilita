"""Testes de isolamento multi-tenant (História H19 / Requisito RNF01).

Especificação:
- História: H19 (Isolar dados por cliente e papel)
- Requisito Não Funcional: RNF01 (Autorização por cliente e papel em 100% das rotas)
- ADRs Relacionadas: ADR 0002 (Multi-tenant e autorização), ADR 0008 (Portaria), ADR 0010/0011
- Casos de Teste da Estratégia de QA: T-ISO-01 a T-ISO-10
- Referência: docs/testes/estrategia.md (Seção 5) e seed/README.md (Seção 4)
"""

import os
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from .conftest import (
    CPF_TRB_BETA_1,
    CTR_ALFA_1,
    CTR_BETA_1,
    DOC_ALFA_1_ASO,
    DOC_BETA_1_ASO,
    TER_ALFA_1,
    TNT_ALFA,
    TNT_BETA,
    TRB_ALFA_1,
    TRB_ALFA_Y1,
    TRB_BETA_1,
)


def _verificar_skip_emulador(servico: str) -> None:
    """Apenas pula o teste se a variável explícita HABILITA_SEM_EMULADOR=1 for fornecida.

    Conforme o novo AGENTS.md (#35), skip silencioso por ConnectError não conta
    como teste passando no CI. O teste DEVE falhar se o emulador/serviço estiver ausente
    sem aviso prévio.
    """
    if os.getenv("HABILITA_SEM_EMULADOR") == "1":
        pytest.skip(
            f"Ambiente configurado com HABILITA_SEM_EMULADOR=1: ignorando teste de {servico}."
        )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "Rotas /contratos/{id}, /trabalhadores/{id} e /documentos/{id} inexistentes (Semana 4). "
        "Atualmente retornam 404 de rota não encontrada do FastAPI em vez do 404 Problem Details "
        "(RFC 9457, application/problem+json) da camada de autorização."
    ),
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
        assert TNT_BETA not in corpo_texto, f"Vazamento de tenantId de B em {rota}!"
        assert "beta" not in corpo_texto or "detail" in corpo_texto, (
            f"Vazamento de dados do recurso de B no corpo da resposta em {rota}."
        )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
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

        for item in itens:
            item_str = str(item).lower()
            assert "beta" not in item_str, f"Recurso do Tenant Beta vazou na listagem de {rota}!"
            assert item.get("tenantId", TNT_ALFA) == TNT_ALFA


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Rota POST /contratos prevista para implementação na Semana 4 (ADR 0002).",
)
def test_h19_ca5_t_iso_03a_injecao_tenant_id_no_corpo_rejeitada_ou_isolada(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """T-ISO-03a (H19.CA5): Tentativa de injeção de tenantId no corpo JSON da requisição.

    Dado:
        Um usuário autenticado do Tenant Alfa (tnt_alfa).
    Quando:
        O usuário tenta criar um contrato enviando tenantId='tnt_beta' no payload JSON.
    Então:
        A API rejeita o campo extra (400/422 via extra='forbid') ou ignora o campo
        e persiste o recurso exclusivamente no tenant da claim (tnt_alfa).
    """
    payload_com_injecao = {
        "identificador": "CTR-TEST-INJECTION-BODY-01",
        "terceirizadaId": TER_ALFA_1,
        "tenantId": TNT_BETA,
    }

    resposta = client.post("/contratos", json=payload_com_injecao, headers=headers_gestor_alfa)

    assert resposta.status_code in (201, 400, 422), (
        f"Código inesperado na tentativa de injeção via body: {resposta.status_code}"
    )

    if resposta.status_code == 201:
        contrato_criado: dict[str, Any] = resposta.json()
        assert contrato_criado.get("tenantId") != TNT_BETA, (
            "VULNERABILIDADE CRÍTICA: Contrato criado no tenant injetado (tnt_beta) via body!"
        )
        assert contrato_criado.get("tenantId", TNT_ALFA) == TNT_ALFA


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Rota POST /contratos prevista para implementação na Semana 4 (ADR 0002).",
)
def test_h19_ca5_t_iso_03b_injecao_tenant_id_na_query_rejeitada_ou_isolada(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """T-ISO-03b (H19.CA5): Tentativa de injeção de tenantId via query parameter.

    Dado:
        Um usuário autenticado do Tenant Alfa (tnt_alfa).
    Quando:
        O usuário tenta criar um contrato chamando POST /contratos?tenantId=tnt_beta.
    Então:
        A query string é ignorada ou rejeitada, mantendo a persistência em Alfa.
    """
    payload_valido = {
        "identificador": "CTR-TEST-INJECTION-QUERY-01",
        "terceirizadaId": TER_ALFA_1,
    }

    resposta = client.post(
        "/contratos?tenantId=tnt_beta",
        json=payload_valido,
        headers=headers_gestor_alfa,
    )

    assert resposta.status_code in (201, 400, 422), (
        f"Código inesperado na tentativa de injeção via query: {resposta.status_code}"
    )

    if resposta.status_code == 201:
        contrato_criado: dict[str, Any] = resposta.json()
        assert contrato_criado.get("tenantId") != TNT_BETA, (
            "VULNERABILIDADE CRÍTICA: Contrato criado no tenant injetado via query!"
        )
        assert contrato_criado.get("tenantId", TNT_ALFA) == TNT_ALFA


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Rota POST /contratos prevista para implementação na Semana 4 (ADR 0002).",
)
def test_h19_ca5_t_iso_03c_injecao_tenant_id_no_header_rejeitada_ou_isolada(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """T-ISO-03c (H19.CA5): Tentativa de injeção de tenantId via cabeçalho HTTP (X-Tenant-Id).

    Dado:
        Um usuário autenticado do Tenant Alfa (tnt_alfa).
    Quando:
        O usuário tenta criar contrato enviando header X-Tenant-Id: tnt_beta.
    Então:
        O cabeçalho externo é desconsiderado; a autorização usa unicamente a claim do token.
    """
    payload_valido = {
        "identificador": "CTR-TEST-INJECTION-HEADER-01",
        "terceirizadaId": TER_ALFA_1,
    }

    headers_com_injecao = {
        **headers_gestor_alfa,
        "X-Tenant-Id": TNT_BETA,
    }

    resposta = client.post("/contratos", json=payload_valido, headers=headers_com_injecao)

    assert resposta.status_code in (201, 400, 422), (
        f"Código inesperado na injeção via header: {resposta.status_code}"
    )

    if resposta.status_code == 201:
        contrato_criado: dict[str, Any] = resposta.json()
        assert contrato_criado.get("tenantId") != TNT_BETA, (
            "VULNERABILIDADE CRÍTICA: Contrato criado no tenant injetado via header!"
        )
        assert contrato_criado.get("tenantId", TNT_ALFA) == TNT_ALFA


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Rota POST /contratos e validação de claims previstos para Semana 4.",
)
def test_h19_ca5_t_iso_03d_header_simulado_com_token_divergente_rejeitado_ou_isolado(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """T-ISO-03d (H19.CA5): Tentativa com X-Simulated-Tenant-Id divergente do token de A.

    Dado:
        Um usuário autenticado com token do Tenant Alfa (tnt_alfa).
    Quando:
        Envia o cabeçalho X-Simulated-Tenant-Id: tnt_beta para tentar burlar o contexto.
    Então:
        A API prioriza a claim do token ou rejeita a requisição, nunca criando dados em B.
    """
    payload_valido = {
        "identificador": "CTR-TEST-SIMULATED-DIVERGENT-01",
        "terceirizadaId": TER_ALFA_1,
    }

    headers_divergentes = {
        **headers_gestor_alfa,
        "X-Simulated-Tenant-Id": TNT_BETA,
    }

    resposta = client.post("/contratos", json=payload_valido, headers=headers_divergentes)

    assert resposta.status_code in (201, 400, 401, 403, 422), (
        f"Código inesperado com header simulado divergente: {resposta.status_code}"
    )

    if resposta.status_code == 201:
        contrato_criado: dict[str, Any] = resposta.json()
        assert contrato_criado.get("tenantId") != TNT_BETA, (
            "VULNERABILIDADE CRÍTICA: Token de A operou no contexto do tenant B!"
        )
        assert contrato_criado.get("tenantId", TNT_ALFA) == TNT_ALFA


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
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
        A consulta responde 200 com resultado='NAO_CADASTRADO'.
        Conforme a ADR 0008, a resposta nunca deve conter dados de documento, contrato,
        nem dados confidenciais do trabalhador do Tenant Beta.
    """
    payload_consulta = {
        "cpf": CPF_TRB_BETA_1,
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

    # Conforme ADR 0008, a resposta nunca deve expor dados de trabalhador, documentos ou contratos
    assert "trabalhador" not in resultado or resultado.get("trabalhador") is None
    assert "contratos" not in resultado
    assert "documentos" not in resultado
    assert "contratosAptos" not in resultado
    assert "Alexandre Pires Barbosa" not in resposta.text


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "Rota GET /trabalhadores/{id} inexistente (Semana 4). "
        "Atualmente retorna 404 de rota não encontrada do FastAPI em vez do 404 Problem Details "
        "(RFC 9457, application/problem+json) da camada de autorização."
    ),
)
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


def test_h19_ca4_t_iso_06a_acesso_direto_firestore_sem_api_rejeitado_deny_all() -> None:
    """T-ISO-06a (H19.CA4): Regras deny-all no emulador bloqueiam acesso direto ao Firestore.

    Dado:
        O navegador ou cliente externo tentando ler ou escrever diretamente
        no Firestore sem passar pela API FastAPI.
    Quando:
        Operações de leitura (GET) e escrita (POST) não autenticadas são executadas
        diretamente contra a API REST do Firestore emulador.
    Então:
        1. Firestore rejeita leitura não autenticada com HTTP 403 (PERMISSION_DENIED).
        2. Firestore rejeita escrita não autenticada com HTTP 403 (PERMISSION_DENIED).
        Comprova a diretiva deny-all em tempo de execução sem skip silencioso.
    """
    _verificar_skip_emulador("Firestore")

    firestore_host = os.getenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    firestore_base = (
        firestore_host.rstrip("/") if "://" in firestore_host else f"http://{firestore_host}"
    )
    project_id = os.getenv("FIREBASE_PROJECT_ID", "demo-habilita")
    probe_doc = "probe_t_iso_06a"
    url_fs_docs = (
        f"{firestore_base}/v1/projects/{project_id}/databases/(default)/documents/{probe_doc}"
    )

    with httpx.Client(timeout=5.0) as http_client:
        # 1. Firestore: leitura não autenticada negada
        resp_fs_read = http_client.get(url_fs_docs)
        assert resp_fs_read.status_code == 403, (
            f"Esperado HTTP 403 na leitura do Firestore, obtido {resp_fs_read.status_code}"
        )
        fs_read_json = resp_fs_read.json()
        assert fs_read_json.get("error", {}).get("status") == "PERMISSION_DENIED", (
            f"Esperado PERMISSION_DENIED no Firestore, obtido: {fs_read_json}"
        )

        # 2. Firestore: escrita não autenticada negada
        resp_fs_write = http_client.post(
            url_fs_docs,
            json={"fields": {"probe": {"stringValue": "t_iso_06a_unauthenticated"}}},
        )
        assert resp_fs_write.status_code == 403, (
            f"Esperado HTTP 403 na escrita do Firestore, obtido {resp_fs_write.status_code}"
        )
        fs_write_json = resp_fs_write.json()
        assert fs_write_json.get("error", {}).get("status") == "PERMISSION_DENIED", (
            f"Esperado PERMISSION_DENIED no Firestore, obtido: {fs_write_json}"
        )


def test_h19_ca4_t_iso_06b_acesso_direto_storage_sem_api_rejeitado_deny_all() -> None:
    """T-ISO-06b (H19.CA4): Acesso direto ao Storage sem passar pela API é recusado.

    Dado:
        O navegador ou cliente externo tentando ler, escrever ou listar objetos
        diretamente no backend de arquivos (Supabase Storage local ou Firebase Storage).
    Quando:
        Operações não autenticadas ou com chave pública anon são executadas diretamente.
    Então:
        O Storage rejeita leitura, escrita e listagem (HTTP 400/401/403/404),
        garantindo que o bucket de documentos é estritamente privado (ADR 0006/0011).
    """
    _verificar_skip_emulador("Storage")

    # Verifica se o Supabase Storage está ativo
    storage_url = (
        os.getenv("STORAGE_PUBLIC_URL") or os.getenv("STORAGE_URL") or "http://127.0.0.1:5000"
    ).rstrip("/")
    bucket_nome = os.getenv("STORAGE_BUCKET", "documentos")
    anon_key = os.getenv(
        "STORAGE_ANON_KEY",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic"
        "3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_"
        "X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE",
    )

    probe_nome = "probe_t_iso_06b.txt"

    with httpx.Client(timeout=5.0) as http_client:
        # Detecta se está rodando com Supabase Storage ou Firebase Storage
        is_supabase = False
        try:
            status_resp = http_client.get(f"{storage_url}/status")
            if status_resp.status_code == 200:
                is_supabase = True
        except Exception:
            is_supabase = False

        if is_supabase:
            # 1. Supabase: listagem anônima recusada
            url_list = f"{storage_url}/storage/v1/object/list/{bucket_nome}"
            resp_list_anon = http_client.get(url_list)
            assert resp_list_anon.status_code in (400, 401, 403), (
                f"Esperado erro de autorização na listagem anônima: {resp_list_anon.status_code}"
            )

            # 2. Supabase: leitura anônima direta recusada
            url_obj = f"{storage_url}/storage/v1/object/{bucket_nome}/{probe_nome}"
            resp_read_anon = http_client.get(url_obj)
            assert resp_read_anon.status_code in (400, 401, 403, 404), (
                f"Esperado erro na leitura anônima direta: {resp_read_anon.status_code}"
            )

            # 3. Supabase: listagem com chave anon (sem RLS permitindo anon) recusada
            headers_anon = {"Authorization": f"Bearer {anon_key}", "apikey": anon_key}
            resp_list_key = http_client.get(url_list, headers=headers_anon)
            assert resp_list_key.status_code in (400, 401, 403), (
                f"Esperado erro na listagem com chave anon: {resp_list_key.status_code}"
            )

            # 4. Supabase: escrita anônima recusada
            resp_write_anon = http_client.post(
                url_obj,
                content=b"dados_proibidos",
                headers={"Content-Type": "text/plain"},
            )
            assert resp_write_anon.status_code in (400, 401, 403), (
                f"Esperado erro na escrita anônima no Supabase: {resp_write_anon.status_code}"
            )
        else:
            # Fallback para o emulador do Firebase Storage (porta 9199)
            storage_host = (
                os.getenv("FIREBASE_STORAGE_EMULATOR_HOST")
                or os.getenv("STORAGE_EMULATOR_HOST")
                or "127.0.0.1:9199"
            )
            storage_base = (
                storage_host.rstrip("/") if "://" in storage_host else f"http://{storage_host}"
            )
            project_id = os.getenv("FIREBASE_PROJECT_ID", "demo-habilita")
            fb_bucket = os.getenv("STORAGE_BUCKET_NAME", f"{project_id}.appspot.com")
            url_st_file = f"{storage_base}/v0/b/{fb_bucket}/o/{probe_nome}"
            url_st_upload = f"{storage_base}/v0/b/{fb_bucket}/o?name={probe_nome}"

            resp_st_read = http_client.get(url_st_file)
            assert resp_st_read.status_code == 403, (
                f"Esperado HTTP 403 na leitura do Storage Firebase: {resp_st_read.status_code}"
            )

            resp_st_write = http_client.post(
                url_st_upload,
                content=b"dados_nao_autenticados_t_iso_06b",
                headers={"Content-Type": "text/plain"},
            )
            assert resp_st_write.status_code == 403, (
                f"Esperado HTTP 403 na escrita do Storage Firebase: {resp_st_write.status_code}"
            )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "Rota POST /documentos/{id}/url-download inexistente (Semana 4). "
        "Atualmente retorna 404 de rota não encontrada do FastAPI em vez do 404 Problem Details "
        "(RFC 9457, application/problem+json) da camada de autorização."
    ),
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


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "Rotas protegidas e middleware de autenticação previstos para Semana 4. "
        "Atualmente rota inexistente retorna 404 de rota não encontrada em vez de "
        "401 Problem Details da camada de autenticação."
    ),
)
def test_h19_t_iso_08_requisicao_sem_token_retorna_401_problem_details(
    client: TestClient,
) -> None:
    """T-ISO-08 (H19): Requisição a rotas protegidas sem token retorna 401 Problem Details.

    Dado:
        Um cliente não autenticado (sem cabeçalho Authorization nem token).
    Quando:
        Tenta acessar endpoints protegidos de contratos, trabalhadores ou documentos:
        - GET /contratos/{id}
        - GET /trabalhadores/{id}
        - GET /documentos
    Então:
        A API responde HTTP 401 Unauthorized com formato Problem Details (RFC 9457,
        application/problem+json) e status 401 no payload.
    """
    rotas_protegidas = [
        f"/contratos/{CTR_ALFA_1}",
        f"/trabalhadores/{TRB_ALFA_1}",
        "/documentos",
    ]

    for rota in rotas_protegidas:
        resposta = client.get(rota)

        assert resposta.status_code == 401, (
            f"Esperado HTTP 401 para requisição sem token em {rota}, "
            f"mas obteve HTTP {resposta.status_code}."
        )
        assert "application/problem+json" in resposta.headers.get("content-type", ""), (
            f"Esperado Content-Type 'application/problem+json' em {rota}, "
            f"mas obteve '{resposta.headers.get('content-type')}'."
        )
        corpo = resposta.json()
        assert corpo.get("status") == 401, (
            f"Esperado status 401 em {rota}, mas obteve {corpo.get('status')}."
        )
        assert "title" in corpo or "type" in corpo, (
            f"Corpo da resposta em {rota} não segue o padrão Problem Details: {corpo}"
        )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "Controle de acesso baseado em papel (RBAC) previsto para Semana 4. "
        "Atualmente rota inexistente retorna 404 de rota não encontrada em vez de "
        "403 Problem Details da camada de autorização."
    ),
)
def test_h19_ca2_t_iso_09_papel_inadequado_retorna_403_problem_details(
    client: TestClient,
    headers_porteiro_alfa: dict[str, str],
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """T-ISO-09 (H19.CA2): Requisições de usuários com papel não autorizado retornam 403.

    Dado:
        Usuários autenticados com papéis específicos ('porteiro' ou 'terceirizada').
    Quando:
        - Porteiro tenta criar contrato (POST /contratos) ou aprovar documento.
        - Terceirizada tenta aprovar documento de SST (POST /documentos/{id}/aprovacao).
    Então:
        A API responde HTTP 403 Forbidden com formato Problem Details (RFC 9457,
        application/problem+json), garantindo que violações de RBAC sejam bloqueadas.
    """
    # 1. Porteiro tenta criar contrato (ação restrita a Gestor SST)
    payload_contrato = {
        "identificador": "CTR-ILLEGAL-01",
        "terceirizadaId": TER_ALFA_1,
    }
    resp_porteiro = client.post(
        "/contratos",
        json=payload_contrato,
        headers=headers_porteiro_alfa,
    )
    assert resp_porteiro.status_code == 403, (
        f"Esperado HTTP 403 para porteiro criando contrato, mas obteve {resp_porteiro.status_code}."
    )
    assert "application/problem+json" in resp_porteiro.headers.get("content-type", ""), (
        f"Esperado application/problem+json em POST /contratos, "
        f"mas obteve '{resp_porteiro.headers.get('content-type')}'."
    )
    assert resp_porteiro.json().get("status") == 403

    # 2. Terceirizada tenta aprovar documento (ação restrita a Gestor SST)
    resp_terceirizada = client.post(
        f"/documentos/{DOC_ALFA_1_ASO}/aprovacao",
        headers=headers_terceirizada_1_alfa,
    )
    assert resp_terceirizada.status_code == 403, (
        f"Esperado HTTP 403 para terceirizada aprovando documento, "
        f"mas obteve {resp_terceirizada.status_code}."
    )
    assert "application/problem+json" in resp_terceirizada.headers.get("content-type", ""), (
        f"Esperado application/problem+json em aprovação de documento, "
        f"mas obteve '{resp_terceirizada.headers.get('content-type')}'."
    )
    assert resp_terceirizada.json().get("status") == 403


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "Rotas e repositórios delimitados por caminho previstos para Semana 4. "
        "Atualmente rota inexistente retorna 404 de rota não encontrada em vez do "
        "404 Problem Details da camada de autorização."
    ),
)
def test_h19_ca1_t_iso_10_ids_parecidos_ou_colidentes_entre_tenants_retorna_404(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """T-ISO-10 (H19.CA1): IDs parecidos, colidentes ou com prefixos similares retornam 404.

    Dado:
        Um usuário autenticado como Gestor SST do Tenant Alfa (tnt_alfa).
    Quando:
        O gestor tenta acessar recursos cujos IDs se assemelham aos de Alfa,
        colidem em nome simples ou tentam path traversal:
        - GET /contratos/{id_beta_parecido} (ex.: 'ctr_beta_1' vs 'ctr_alfa_1')
        - GET /contratos/{id_com_sufixo_ou_prefixo}
        - GET /contratos/{tentativa_path_traversal_com_percent_encoding}
    Então:
        A busca delimitada sob 'tenants/tnt_alfa/...' responde HTTP 404 com formato
        Problem Details (RFC 9457), garantindo que correspondências parciais,
        colisões ou prefixos parecidos nunca vazem dados entre tenants.
    """
    ids_fronteira = [
        CTR_BETA_1,
        f"{CTR_ALFA_1}_beta",
        f"beta_{CTR_ALFA_1}",
        f"..%2Ftnt_beta%2Fcontratos%2F{CTR_BETA_1}",
        f"%2e%2e%2ftnt_beta%2fcontratos%2f{CTR_BETA_1}",
    ]

    for recurso_id in ids_fronteira:
        rota = f"/contratos/{recurso_id}"
        resposta = client.get(rota, headers=headers_gestor_alfa)

        assert resposta.status_code == 404, (
            f"Esperado HTTP 404 para ID fronteira/parecido '{recurso_id}' em {rota}, "
            f"mas obteve HTTP {resposta.status_code}."
        )
        assert "application/problem+json" in resposta.headers.get("content-type", ""), (
            f"Esperado Content-Type 'application/problem+json' em {rota}, "
            f"mas obteve '{resposta.headers.get('content-type')}'."
        )
        corpo = resposta.json()
        assert corpo.get("status") == 404
        assert "title" in corpo or "type" in corpo
        assert TNT_BETA not in resposta.text.lower(), f"Vazamento de tenantId de B em {rota}!"


# =============================================================================
# Casos de Segurança e Controle de Acesso Adicionais do Checkpoint 2
# =============================================================================


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Middleware de autenticação com validação estrita de token previsto para Semana 4.",
)
def test_h19_token_invalido_retorna_401_problem_details(
    client: TestClient,
    headers_token_invalido: dict[str, str],
) -> None:
    """Valida que tokens malformados ou inválidos são rejeitados com HTTP 401."""
    resposta = client.get(f"/contratos/{CTR_ALFA_1}", headers=headers_token_invalido)
    assert resposta.status_code == 401, (
        f"Esperado HTTP 401 para token inválido, obtido {resposta.status_code}"
    )
    assert "application/problem+json" in resposta.headers.get("content-type", "")
    corpo = resposta.json()
    assert corpo.get("status") == 401


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Middleware de autenticação com validação de expiração previsto para Semana 4.",
)
def test_h19_token_expirado_retorna_401_problem_details(
    client: TestClient,
    headers_token_expirado: dict[str, str],
) -> None:
    """Valida que tokens expirados são rejeitados com HTTP 401."""
    resposta = client.get(f"/contratos/{CTR_ALFA_1}", headers=headers_token_expirado)
    assert resposta.status_code == 401, (
        f"Esperado HTTP 401 para token expirado, obtido {resposta.status_code}"
    )
    assert "application/problem+json" in resposta.headers.get("content-type", "")
    corpo = resposta.json()
    assert corpo.get("status") == 401


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="Controle de acesso por papel na edição de exigências previsto para Semana 4.",
)
def test_h19_ca2_analista_sst_altera_exigencias_retorna_403(
    client: TestClient,
    headers_analista_sst_alfa: dict[str, str],
) -> None:
    """Papel analista_sst não tem permissão para alterar exigências do contrato (ADR 0002).

    Conforme a ADR 0002 e o novo AGENTS.md:
    Só admin_contratante (gestor) cria contratos e edita a matriz de exigências;
    analista_sst aprova ou rejeita documentos e NÃO edita a matriz.
    """
    payload_exigencias = {
        "tipoDocumentoIds": ["tip_aso"],
    }
    resposta = client.put(
        f"/contratos/{CTR_ALFA_1}/exigencias",
        json=payload_exigencias,
        headers=headers_analista_sst_alfa,
    )
    assert resposta.status_code == 403, (
        f"Esperado HTTP 403 para analista_sst tentando alterar exigências, "
        f"obtido {resposta.status_code}"
    )
    assert "application/problem+json" in resposta.headers.get("content-type", "")
    corpo = resposta.json()
    assert corpo.get("status") == 403
