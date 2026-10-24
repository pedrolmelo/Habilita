"""Schemas Pydantic v2 para as Jornadas J2 e J3 (Trabalhadores e Documentos).

Conforme o contrato da API e a ADR 0002/0008:
- CPF nunca exposto em texto claro (cpfMascarado).
- Metadados de arquivos (tipo verificado por bytes, tamanho e sha256).
- extra="forbid" em todos os modelos de entrada.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NovoTrabalhador(BaseModel):
    """Payload de cadastro de trabalhador."""

    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=3, max_length=120)
    cpf: str = Field(description="CPF do trabalhador com 11 dígitos")
    terceirizadaId: str | None = Field(
        default=None,
        description="Obrigatório para gestor; ignorado/sobrescrito para terceirizada",
    )

    @field_validator("cpf")
    @classmethod
    def validar_cpf(cls, v: str) -> str:
        digitos = re.sub(r"\D", "", v)
        if len(digitos) != 11:
            raise ValueError("CPF deve conter exatamente 11 dígitos numéricos.")
        return digitos


class Trabalhador(BaseModel):
    """Representação resumida do trabalhador."""

    model_config = ConfigDict(extra="forbid")

    id: str
    terceirizadaId: str
    nome: str
    cpfMascarado: str
    ativo: bool


class Pendencia(BaseModel):
    """Representação de pendência documental."""

    model_config = ConfigDict(extra="forbid")

    tipoDocumentoId: str
    tipoNome: str
    motivo: str


class Alocacao(BaseModel):
    """Vínculo de trabalhador com contrato e semáforo."""

    model_config = ConfigDict(extra="forbid")

    contratoId: str
    trabalhadorId: str
    semaforo: Literal["VERDE", "AMARELO", "VERMELHO"]
    pendencias: list[Pendencia] = Field(default_factory=list)
    calculadoEm: str
    proximoVencimento: str | None = None


class ArquivoMetadados(BaseModel):
    """Metadados de arquivo armazenado no Storage."""

    model_config = ConfigDict(extra="forbid")

    contentType: Literal["application/pdf", "image/jpeg", "image/png"]
    tamanhoBytes: int = Field(ge=1, le=10485760)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Documento(BaseModel):
    """Representação de um documento comprobatório de SST."""

    model_config = ConfigDict(extra="forbid")

    id: str
    trabalhadorId: str
    tipoDocumentoId: str
    validoAte: str
    statusRevisao: Literal["PENDENTE", "APROVADO", "REJEITADO"]
    enviadoEm: str
    dataEmissao: str | None = None
    revisadoEm: str | None = None
    motivoRejeicao: str | None = None
    situacaoValidade: str | None = None
    arquivo: ArquivoMetadados | None = None


class TrabalhadorDetalhe(BaseModel):
    """Detalhes completos do trabalhador com seus documentos e alocações."""

    model_config = ConfigDict(extra="forbid")

    id: str
    terceirizadaId: str
    nome: str
    cpfMascarado: str
    ativo: bool
    documentos: list[Documento] = Field(default_factory=list)
    alocacoes: list[Alocacao] = Field(default_factory=list)


class NovaAlocacao(BaseModel):
    """Payload para vincular trabalhador ao contrato."""

    model_config = ConfigDict(extra="forbid")

    trabalhadorId: str = Field(min_length=1)


class RejeitarDocumentoPayload(BaseModel):
    """Payload de rejeição de documento com justificativa obrigatória."""

    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(min_length=5, max_length=500)


class UrlDownloadResponse(BaseModel):
    """URL assinada para download temporário do documento."""

    model_config = ConfigDict(extra="forbid")

    url: str
    expiraEm: str
