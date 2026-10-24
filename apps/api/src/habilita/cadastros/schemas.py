"""Schemas Pydantic v2 para a Jornada J1 (Cadastros e Contratos).

Todos os schemas de entrada usam `extra="forbid"` para impedir campos espúrios
e tentativas de injeção de `tenantId` (ADR 0002 / T-ISO-03).
"""

from __future__ import annotations

import re
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):  # noqa: UP046
    """Envelope de listagem paginada por cursor."""

    model_config = ConfigDict(extra="forbid")

    itens: list[T]
    proximoCursor: str | None = None


# -----------------------------------------------------------------------------
# Terceirizadas
# -----------------------------------------------------------------------------
class NovaTerceirizada(BaseModel):
    """Payload de criação de terceirizada."""

    model_config = ConfigDict(extra="forbid")

    razaoSocial: str = Field(min_length=3, max_length=150)
    cnpj: str = Field(description="CNPJ da empresa terceirizada (14 dígitos com ou sem pontuação)")

    @field_validator("cnpj")
    @classmethod
    def validar_e_normalizar_cnpj(cls, v: str) -> str:
        digitos = re.sub(r"\D", "", v)
        if len(digitos) != 14:
            raise ValueError("CNPJ deve conter exatamente 14 dígitos numéricos.")
        return digitos


class Terceirizada(BaseModel):
    """Representação de terceirizada."""

    model_config = ConfigDict(extra="forbid")

    id: str
    razaoSocial: str
    cnpj: str
    ativa: bool


# -----------------------------------------------------------------------------
# Tipos de Documento
# -----------------------------------------------------------------------------
class NovoTipoDocumento(BaseModel):
    """Payload de criação de tipo de documento."""

    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=2, max_length=80)
    validadeMeses: int = Field(ge=1, le=120)


class TipoDocumento(BaseModel):
    """Representação de tipo de documento."""

    model_config = ConfigDict(extra="forbid")

    id: str
    nome: str
    validadeMeses: int


class ListaTiposDocumento(BaseModel):
    """Listagem de tipos de documento."""

    model_config = ConfigDict(extra="forbid")

    itens: list[TipoDocumento]


# -----------------------------------------------------------------------------
# Contratos
# -----------------------------------------------------------------------------
class NovoContrato(BaseModel):
    """Payload de criação de contrato."""

    model_config = ConfigDict(extra="forbid")

    identificador: str = Field(min_length=1, max_length=40)
    terceirizadaId: str = Field(min_length=1)
    dataInicio: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    dataFim: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class SubstituirExigencias(BaseModel):
    """Payload para substituição da matriz de exigências do contrato."""

    model_config = ConfigDict(extra="forbid")

    tipoDocumentoIds: list[str] = Field(min_length=1, max_length=20)


class Contrato(BaseModel):
    """Representação completa de um contrato com sua matriz de exigências."""

    model_config = ConfigDict(extra="forbid")

    id: str
    identificador: str
    terceirizadaId: str
    dataInicio: str
    dataFim: str
    vigente: bool
    versaoMatriz: int
    exigencias: list[TipoDocumento]
