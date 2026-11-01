"""Testes de saúde, sessão (/me), paginação e tratamento de erros (RFC 9457).

Cobre:
- /healthz e /readyz respondendo sem login (HTTP 200)
- /me respondendo dados do usuário conforme claims (HTTP 200)
- /me respondendo HTTP 401 Problem Details sem header Authorization
- Extra fields rejeitados com HTTP 422 Problem Details (extra="forbid")
- Limite de paginação obedecido e refletido nas respostas
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import TNT_ALFA


def test_healthz_e_readyz_sem_autenticacao(client: TestClient) -> None:
    """Rotas públicas de infraestrutura respondem 200 sem necessidade de login."""
    resp_health = client.get("/healthz")
    assert resp_health.status_code == 200
    assert resp_health.json() == {"status": "ok"}
    assert "x-request-id" in resp_health.headers

    resp_ready = client.get("/readyz")
    assert resp_ready.status_code == 200
    assert resp_ready.json() == {"status": "ok"}
    assert "x-request-id" in resp_ready.headers


def test_me_usuario_autenticado_retorna_perfil(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """GET /me retorna dados do usuário autenticado a partir das custom claims."""
    resp = client.get("/me", headers=headers_gestor_alfa)
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["tenantId"] == TNT_ALFA
    assert corpo["papel"] == "gestor"
    assert "uid" in corpo


def test_me_sem_token_retorna_401_problem_details(client: TestClient) -> None:
    """Acesso sem token em rota protegida responde HTTP 401 Problem Details."""
    resp = client.get("/me")
    assert resp.status_code == 401
    assert "application/problem+json" in resp.headers.get("content-type", "")
    corpo = resp.json()
    assert corpo.get("status") == 401
    assert "title" in corpo


def test_corpo_invalido_com_campos_extras_retorna_422_problem_details(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """Campos extras são expressamente proibidos (extra='forbid') gerando HTTP 422."""
    payload_invalido = {
        "nome": "Tipo Válido",
        "obrigatorio": True,
        "campo_fantasma_malicioso": "proibido",
    }
    resp = client.post("/tipos-documento", json=payload_invalido, headers=headers_gestor_alfa)
    assert resp.status_code == 422
    assert "application/problem+json" in resp.headers.get("content-type", "")
    corpo = resp.json()
    assert corpo.get("status") == 422
    assert "extra inputs are not permitted" in str(corpo).lower()


def test_paginacao_limite_e_cursor(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """Verifica comportamento dos parâmetros de limite e estrutura de paginação."""
    resp = client.get("/terceirizadas?limite=1", headers=headers_gestor_alfa)
    assert resp.status_code == 200
    dados = resp.json()
    assert "itens" in dados
    assert len(dados["itens"]) <= 1
    assert "proximoCursor" in dados
