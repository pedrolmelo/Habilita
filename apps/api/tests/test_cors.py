"""Testes unitários de CORS para a API do Habilita.

Verifica se origens autorizadas (ex: o frontend local em http://localhost:5173)
recebem os cabeçalhos de preflight e resposta CORS adequados, e se origens
não autorizadas são rejeitadas.

Também valida o parse de CORS_ORIGINS via variável de ambiente (CSV com NoDecode),
a rejeição de '*' e as regras estritas de produção (ADR 0010, exceção 2).
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from habilita.config import Settings
from habilita.main import create_app


def test_cors_preflight_origem_autorizada_retorna_headers_cors() -> None:
    app = create_app()
    client = TestClient(app)
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization,Content-Type",
    }

    response = client.options("/healthz", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    # allow_credentials=False não deve retornar access-control-allow-credentials: true
    assert "access-control-allow-credentials" not in response.headers
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "GET" in allow_methods
    assert "OPTIONS" in allow_methods


def test_cors_requisicao_get_origem_autorizada_retorna_allow_origin() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/healthz", headers={"Origin": "http://127.0.0.1:5173"})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert "access-control-allow-credentials" not in response.headers


def test_cors_origem_nao_autorizada_nao_recebe_headers_cors() -> None:
    app = create_app()
    client = TestClient(app)
    headers = {
        "Origin": "http://origem-maliciosa.com",
        "Access-Control-Request-Method": "GET",
    }

    response = client.options("/healthz", headers=headers)

    # Quando a origem não é autorizada, o FastAPI não adiciona access-control-allow-origin
    assert "access-control-allow-origin" not in response.headers


def test_cors_origins_csv_com_nodecode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que CORS_ORIGINS fornecida em CSV sem formato JSON é parseada corretamente."""
    monkeypatch.setenv("CORS_ORIGINS", "http://a,http://b")
    settings = Settings()
    assert settings.cors_origins == ["http://a", "http://b"]


def test_cors_origins_recusa_asterisco(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validador deve recusar wildcard '*' por segurança."""
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValidationError, match="A origem '\\*' não é permitida"):
        Settings()

    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,*")
    with pytest.raises(ValidationError, match="A origem '\\*' não é permitida"):
        Settings()


def test_cors_origins_em_producao_exige_https_e_nao_vazio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Em produção (APP_ENV=prod), CORS_ORIGINS não pode ser vazia e exige HTTPS."""
    monkeypatch.setenv("APP_ENV", "prod")

    # Lista vazia é rejeitada
    monkeypatch.setenv("CORS_ORIGINS", "")
    with pytest.raises(ValidationError, match="CORS_ORIGINS não pode ser vazia"):
        Settings()

    # Origem com HTTP em prod é rejeitada
    monkeypatch.setenv("CORS_ORIGINS", "http://app.habilita.com.br")
    with pytest.raises(ValidationError, match="todas as origens devem usar HTTPS"):
        Settings()

    # Origem válida com HTTPS em prod é aceita
    monkeypatch.setenv("CORS_ORIGINS", "https://app.habilita.com.br,https://gestor.habilita.com.br")
    settings_prod = Settings()
    assert settings_prod.cors_origins == [
        "https://app.habilita.com.br",
        "https://gestor.habilita.com.br",
    ]
