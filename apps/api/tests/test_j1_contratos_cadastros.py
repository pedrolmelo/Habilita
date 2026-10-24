"""Testes de integração para a Jornada J1 (Contratos e Cadastros).

Cobre os requisitos de negócio, controle de acesso e isolamento multi-tenant:
- Gestor cadastra e lista terceirizadas
- Gestor cadastra e lista tipos de documento
- Gestor cria contrato e define matriz de exigências
- Tentativa de injeção de tenantId é rejeitada (422)
- Isolamento vertical (papel sem permissão recebe 403 com problem+json)
- Isolamento horizontal (acesso a dados de outro tenant ou terceirizada recebe 404 com problem+json)
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import CTR_ALFA_1, CTR_BETA_1, TER_ALFA_1


def test_j1_gestor_cria_e_lista_terceirizada(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """Valida cadastro de terceirizada e normalização de CNPJ."""
    payload = {
        "razaoSocial": "Nova Terceirizada Teste Manutenção",
        "cnpj": "12.345.678/0001-95",
    }
    resp_post = client.post("/terceirizadas", json=payload, headers=headers_gestor_alfa)
    assert resp_post.status_code == 201
    ter = resp_post.json()
    assert ter["cnpj"] == "12345678000195"
    assert ter["razaoSocial"] == payload["razaoSocial"]
    assert ter["ativa"] is True
    assert "id" in ter

    resp_get = client.get("/terceirizadas", headers=headers_gestor_alfa)
    assert resp_get.status_code == 200
    dados = resp_get.json()
    assert "itens" in dados
    assert any(item["cnpj"] == "12345678000195" for item in dados["itens"])


def test_j1_papel_terceirizada_nao_pode_criar_terceirizada_retorna_403(
    client: TestClient,
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Papel terceirizada é proibido de cadastrar terceirizadas (apenas gestor)."""
    payload = {
        "razaoSocial": "Tentativa Invasiva",
        "cnpj": "99999999000199",
    }
    resp = client.post("/terceirizadas", json=payload, headers=headers_terceirizada_1_alfa)
    assert resp.status_code == 403
    assert "application/problem+json" in resp.headers.get("content-type", "")
    assert resp.json().get("status") == 403
    assert resp.json().get("title") == "Acesso proibido"


def test_j1_gestor_cria_e_lista_tipos_documento(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Gestor cria tipo de documento; terceirizada pode listar mas não criar."""
    payload = {
        "nome": "Treinamento Espaço Confinado NR-33",
        "validadeMeses": 12,
    }
    resp_post = client.post("/tipos-documento", json=payload, headers=headers_gestor_alfa)
    assert resp_post.status_code == 201
    tipo = resp_post.json()
    assert tipo["nome"] == payload["nome"]
    assert tipo["validadeMeses"] == 12

    # Terceirizada pode consultar os tipos
    resp_get = client.get("/tipos-documento", headers=headers_terceirizada_1_alfa)
    assert resp_get.status_code == 200
    assert any(t["nome"] == payload["nome"] for t in resp_get.json()["itens"])

    # Terceirizada não pode criar tipo
    resp_terc_post = client.post(
        "/tipos-documento", json=payload, headers=headers_terceirizada_1_alfa
    )
    assert resp_terc_post.status_code == 403


def test_j1_gestor_cria_contrato_com_sucesso(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """Gestor cria contrato válido com terceirizada existente."""
    payload = {
        "identificador": "CTR-TESTE-J1-01",
        "terceirizadaId": TER_ALFA_1,
        "dataInicio": "2026-03-01",
        "dataFim": "2027-02-28",
    }
    resp = client.post("/contratos", json=payload, headers=headers_gestor_alfa)
    assert resp.status_code == 201
    ctr = resp.json()
    assert ctr["identificador"] == "CTR-TESTE-J1-01"
    assert ctr["terceirizadaId"] == TER_ALFA_1
    assert ctr["versaoMatriz"] == 0
    assert ctr["exigencias"] == []


def test_j1_injecao_tenant_id_rejeitada_com_422(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """Tentativa de injetar tenantId no corpo da requisição é rejeitada (extra=forbid)."""
    payload_com_injecao = {
        "identificador": "CTR-TEST-INJECTION-02",
        "terceirizadaId": TER_ALFA_1,
        "dataInicio": "2026-01-01",
        "dataFim": "2026-12-31",
        "tenantId": "tnt_beta",  # Tentativa de injeção espúria
    }
    resp = client.post("/contratos", json=payload_com_injecao, headers=headers_gestor_alfa)
    assert resp.status_code == 422
    assert "application/problem+json" in resp.headers.get("content-type", "")
    assert resp.json().get("status") == 422


def test_j1_substituir_matriz_exigencias_contrato(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """Atualização da matriz de exigências incrementa versaoMatriz e vincula documentos."""
    payload_exigencias = {
        "tipoDocumentoIds": ["tip_aso", "tip_nr10"],
    }
    resp = client.put(
        f"/contratos/{CTR_ALFA_1}/exigencias",
        json=payload_exigencias,
        headers=headers_gestor_alfa,
    )
    assert resp.status_code == 200
    ctr = resp.json()
    assert ctr["id"] == CTR_ALFA_1
    assert ctr["versaoMatriz"] >= 2
    nomes_exigidos = [e["id"] for e in ctr["exigencias"]]
    assert "tip_aso" in nomes_exigidos
    assert "tip_nr10" in nomes_exigidos


def test_j1_isolamento_horizontal_contrato_outro_tenant_retorna_404(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """Gestor de Alfa tenta acessar contrato de Beta -> 404 Problem Details."""
    resp = client.get(f"/contratos/{CTR_BETA_1}", headers=headers_gestor_alfa)
    assert resp.status_code == 404
    assert "application/problem+json" in resp.headers.get("content-type", "")
    corpo = resp.json()
    assert corpo.get("status") == 404
    assert corpo.get("title") == "Não encontrado"


def test_j1_isolamento_horizontal_terceirizada_distinta_retorna_404(
    client: TestClient,
    headers_terceirizada_2_alfa: dict[str, str],
) -> None:
    """Terceirizada 2 tenta acessar contrato vinculado exclusivamente à Terceirizada 1 -> 404."""
    resp = client.get(f"/contratos/{CTR_ALFA_1}", headers=headers_terceirizada_2_alfa)
    assert resp.status_code == 404
    assert "application/problem+json" in resp.headers.get("content-type", "")
