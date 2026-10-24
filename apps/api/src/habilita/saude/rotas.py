"""Verificação de vida (`GET /healthz`), conforme o contrato OpenAPI.

Leve de propósito: não acessa Firestore, Storage nem nenhum serviço externo
e não devolve dados pessoais.
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["Sistema"])


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]


class ReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]


@router.get("/healthz", response_model=HealthResponse, operation_id="healthz")
def healthz() -> HealthResponse:
    """Verificação de vida da API."""
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadyResponse, operation_id="readyz")
def readyz() -> ReadyResponse:
    """Verificação de prontidão (dependências acessíveis)."""
    return ReadyResponse(status="ok")
