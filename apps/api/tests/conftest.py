"""Configuração de testes do Pytest para a API do Habilita.

Contém fixtures para o cliente de teste FastAPI e geradores de cabeçalhos
autenticados baseados nas custom claims definidas na ADR 0002.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from habilita.main import app

# -----------------------------------------------------------------------------
# Identificadores canônicos alinhados ao Seed determinístico (seed/README.md)
# -----------------------------------------------------------------------------
TNT_ALFA = "tnt_alfa"
TNT_BETA = "tnt_beta"

TER_ALFA_1 = "ter_alfa_1"
TER_ALFA_2 = "ter_alfa_2"
TER_BETA_1 = "ter_beta_1"
TER_BETA_2 = "ter_beta_2"

CTR_ALFA_1 = "ctr_alfa_1"
CTR_BETA_1 = "ctr_beta_1"

TRB_ALFA_1 = "trb_alfa_1"
TRB_ALFA_Y1 = "trb_alfa_y1"  # Pertence à Terceirizada 2 (ter_alfa_2)
TRB_BETA_1 = "trb_beta_1"

DOC_ALFA_1_ASO = "doc_alfa_1_aso"
DOC_BETA_1_ASO = "doc_beta_1_aso"

CPF_TRB_ALFA_1 = "10100000126"
CPF_TRB_BETA_1 = "20200000160"


def criar_headers_autenticados(
    tenant_id: str,
    papel: str,
    terceirizada_id: str | None = None,
    uid: str | None = None,
) -> dict[str, str]:
    """Cria cabeçalhos simulando autenticação via Bearer token com custom claims.

    Conforme ADR 0002, a API autentica via Firebase ID token e extrai:
    - tenantId: string ('tnt_alfa', 'tnt_beta')
    - papel: 'gestor' | 'terceirizada' | 'porteiro'
    - terceirizadaId: string (obrigatório se papel == 'terceirizada')
    """
    token_simulado = f"mock-token:{tenant_id}:{papel}"
    if terceirizada_id:
        token_simulado += f":{terceirizada_id}"

    headers: dict[str, str] = {
        "Authorization": f"Bearer {token_simulado}",
        "X-Simulated-Tenant-Id": tenant_id,
        "X-Simulated-Papel": papel,
    }
    if terceirizada_id:
        headers["X-Simulated-Terceirizada-Id"] = terceirizada_id
    if uid:
        headers["X-Simulated-UID"] = uid
    return headers


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Fixture que fornece o cliente de teste HTTP para a aplicação FastAPI."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers_gestor_alfa() -> dict[str, str]:
    """Cabeçalhos autenticados para o Gestor SST do Tenant Alfa."""
    return criar_headers_autenticados(
        tenant_id=TNT_ALFA,
        papel="gestor",
        uid="uid_gestor_alfa",
    )


@pytest.fixture
def headers_porteiro_alfa() -> dict[str, str]:
    """Cabeçalhos autenticados para a Portaria do Tenant Alfa."""
    return criar_headers_autenticados(
        tenant_id=TNT_ALFA,
        papel="porteiro",
        uid="uid_porteiro_alfa",
    )


@pytest.fixture
def headers_terceirizada_1_alfa() -> dict[str, str]:
    """Cabeçalhos autenticados para a Terceirizada 1 do Tenant Alfa."""
    return criar_headers_autenticados(
        tenant_id=TNT_ALFA,
        papel="terceirizada",
        terceirizada_id=TER_ALFA_1,
        uid="uid_terc_alfa_1",
    )


@pytest.fixture
def headers_terceirizada_2_alfa() -> dict[str, str]:
    """Cabeçalhos autenticados para a Terceirizada 2 do Tenant Alfa."""
    return criar_headers_autenticados(
        tenant_id=TNT_ALFA,
        papel="terceirizada",
        terceirizada_id=TER_ALFA_2,
        uid="uid_terc_alfa_2",
    )


@pytest.fixture
def headers_gestor_beta() -> dict[str, str]:
    """Cabeçalhos autenticados para o Gestor SST do Tenant Beta."""
    return criar_headers_autenticados(
        tenant_id=TNT_BETA,
        papel="gestor",
        uid="uid_gestor_beta",
    )


@pytest.fixture
def headers_porteiro_beta() -> dict[str, str]:
    """Cabeçalhos autenticados para a Portaria do Tenant Beta."""
    return criar_headers_autenticados(
        tenant_id=TNT_BETA,
        papel="porteiro",
        uid="uid_porteiro_beta",
    )
