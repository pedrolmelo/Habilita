"""Testes unitários de CORS para a API do Habilita.

Verifica se origens autorizadas (ex: o frontend local em http://localhost:5173)
recebem os cabeçalhos de preflight e resposta CORS adequados, e se origens
não autorizadas são rejeitadas.
"""

from fastapi.testclient import TestClient

from habilita.main import app


def test_cors_preflight_origem_autorizada_retorna_headers_cors() -> None:
    client = TestClient(app)
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization,Content-Type",
    }

    response = client.options("/healthz", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "GET" in allow_methods
    assert "OPTIONS" in allow_methods


def test_cors_requisicao_get_origem_autorizada_retorna_allow_origin() -> None:
    client = TestClient(app)
    response = client.get("/healthz", headers={"Origin": "http://127.0.0.1:5173"})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_origem_nao_autorizada_nao_recebe_headers_cors() -> None:
    client = TestClient(app)
    headers = {
        "Origin": "http://origem-maliciosa.com",
        "Access-Control-Request-Method": "GET",
    }

    response = client.options("/healthz", headers=headers)

    # Quando a origem não é autorizada, o FastAPI não adiciona access-control-allow-origin
    assert "access-control-allow-origin" not in response.headers
