"""Configuração de testes do Pytest para a API do Habilita.

Contém fixtures para o cliente de teste FastAPI e geradores de cabeçalhos
autenticados baseados nas custom claims definidas na ADR 0002.
Utiliza app.dependency_overrides[extrair_usuario] conforme convenção FastAPI.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

import pytest
from fastapi import Header
from fastapi.testclient import TestClient

from habilita.comum.auth import UsuarioAutenticado, extrair_usuario
from habilita.comum.erros import nao_autenticado
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


def mock_extrair_usuario(
    authorization: Annotated[str | None, Header()] = None,
) -> UsuarioAutenticado:
    """Substitui extrair_usuario exclusivamente durante testes unitários e de integração."""
    if not authorization or not authorization.startswith("Bearer "):
        raise nao_autenticado("Cabeçalho de autorização Bearer ausente ou inválido.")

    token = authorization.removeprefix("Bearer ").strip()
    partes = token.split(":")

    if len(partes) >= 3 and partes[0] in ("mock-token", "test-token"):
        tenant_id = partes[1]
        papel = partes[2]
        terceirizada_id = partes[3] if len(partes) > 3 and partes[3] else None
        uid = partes[4] if len(partes) > 4 and partes[4] else f"uid_{papel}_{tenant_id}"
        return UsuarioAutenticado(
            uid=uid,
            tenant_id=tenant_id,
            papel=papel,
            terceirizada_id=terceirizada_id,
        )

    raise nao_autenticado("Token de teste inválido.")


def criar_headers_autenticados(
    tenant_id: str,
    papel: str,
    terceirizada_id: str | None = None,
    uid: str | None = None,
) -> dict[str, str]:
    """Cria cabeçalhos simulando autenticação via Bearer token."""
    token = f"test-token:{tenant_id}:{papel}"
    if terceirizada_id:
        token += f":{terceirizada_id}"
    else:
        token += ":"
    if uid:
        token += f":{uid}"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def override_auth_dependency() -> Generator[None, None, None]:
    """Injeta mock_extrair_usuario nas dependências do FastAPI durante todos os testes."""
    app.dependency_overrides[extrair_usuario] = mock_extrair_usuario
    yield
    app.dependency_overrides.pop(extrair_usuario, None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Fixture que fornece o cliente de teste HTTP para a aplicação FastAPI."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers_admin_alfa() -> dict[str, str]:
    """Cabeçalhos autenticados para o Admin Contratante do Tenant Alfa."""
    return criar_headers_autenticados(
        tenant_id=TNT_ALFA,
        papel="admin_contratante",
        uid="uid_admin_alfa",
    )


@pytest.fixture
def headers_analista_alfa() -> dict[str, str]:
    """Cabeçalhos autenticados para o Analista SST do Tenant Alfa."""
    return criar_headers_autenticados(
        tenant_id=TNT_ALFA,
        papel="analista_sst",
        uid="uid_analista_alfa",
    )


@pytest.fixture
def headers_gestor_alfa(headers_admin_alfa: dict[str, str]) -> dict[str, str]:
    """Compatibilidade com fixtures legadas apontando para admin_contratante."""
    return headers_admin_alfa


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
def headers_admin_beta() -> dict[str, str]:
    """Cabeçalhos autenticados para o Admin Contratante do Tenant Beta."""
    return criar_headers_autenticados(
        tenant_id=TNT_BETA,
        papel="admin_contratante",
        uid="uid_admin_beta",
    )


@pytest.fixture
def headers_analista_beta() -> dict[str, str]:
    """Cabeçalhos autenticados para o Analista SST do Tenant Beta."""
    return criar_headers_autenticados(
        tenant_id=TNT_BETA,
        papel="analista_sst",
        uid="uid_analista_beta",
    )


@pytest.fixture
def headers_gestor_beta(headers_admin_beta: dict[str, str]) -> dict[str, str]:
    """Compatibilidade com fixtures legadas apontando para admin_contratante."""
    return headers_admin_beta


@pytest.fixture
def headers_porteiro_beta() -> dict[str, str]:
    """Cabeçalhos autenticados para a Portaria do Tenant Beta."""
    return criar_headers_autenticados(
        tenant_id=TNT_BETA,
        papel="porteiro",
        uid="uid_porteiro_beta",
    )
