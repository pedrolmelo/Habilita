"""Porta e contratos para o serviço de armazenamento de documentos.

Define a interface abstrata (Protocol) que a aplicação utiliza para persistir,
ler e excluir arquivos de documentos de SST, sem acoplamento a provedores específicos.

Conforme a ADR 0006 v3 e o AGENTS.md:
- O tenant_id é injetado no construtor do repositório/adapter (regra de ouro).
- O caminho dos arquivos segue a hierarquia:
    tenants/{tenantId}/trabalhadores/{trabalhadorId}/documentos/{documentoId}/{uuid}.{ext}
  com {uuid}_mini.jpg para a miniatura correspondente.
- A URL assinada de download possui teto máximo de validade de 300 segundos.
"""

from __future__ import annotations

import re
from typing import Literal, Protocol, runtime_checkable

# Padrão seguro para identificadores: apenas alfanuméricos, hífen e sublinhado (1 a 64 chars)
_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

# Padrão seguro para nomes de arquivo: uuid (ou uuid_mini) com extensão pdf ou jpg
_ARQUIVO_REGEX = re.compile(r"^[a-zA-Z0-9_-]+(?:_mini)?\.(?:pdf|jpg)$")

TETO_MAXIMO_EXPIRACAO_SEGUNDOS: int = 300


class ArmazenamentoError(Exception):
    """Exceção base para operações de armazenamento."""


class CaminhoInvalidoError(ArmazenamentoError):
    """Lançada quando identificador contém caracteres inválidos ou path traversal."""


class ObjetoNaoEncontradoError(ArmazenamentoError):
    """Lançada quando o documento solicitado não existe no armazenamento."""


def validar_id(valor: str, nome_campo: str) -> str:
    """Valida identificador contra caracteres maliciosos, quebras de linha e tamanho excessivo."""
    if not valor or not isinstance(valor, str):
        raise CaminhoInvalidoError(f"'{nome_campo}' não pode ser vazio ou nulo.")

    # Verificações expressas contra traversal e separadores de caminho
    if ".." in valor or "/" in valor or "\\" in valor:
        raise CaminhoInvalidoError(
            f"'{nome_campo}' contém caracteres proibidos ou tentativa de path traversal: {valor!r}"
        )

    if not _ID_REGEX.fullmatch(valor):
        raise CaminhoInvalidoError(
            f"'{nome_campo}' contém caracteres inválidos ou excede 64 caracteres: {valor!r}"
        )

    return valor


def construir_caminho(
    tenant_id: str,
    trabalhador_id: str,
    documento_id: str,
    nome_arquivo: str,
) -> str:
    """Constrói o caminho canônico do documento conforme a ADR 0006."""
    t_id = validar_id(tenant_id, "tenant_id")
    trab_id = validar_id(trabalhador_id, "trabalhador_id")
    doc_id = validar_id(documento_id, "documento_id")

    if not nome_arquivo or not _ARQUIVO_REGEX.fullmatch(nome_arquivo):
        raise CaminhoInvalidoError(f"Nome de arquivo inválido: {nome_arquivo!r}")

    return f"tenants/{t_id}/trabalhadores/{trab_id}/documentos/{doc_id}/{nome_arquivo}"


def validar_e_resolver_caminho(
    tenant_id: str,
    caminho: str | None = None,
    trabalhador_id: str | None = None,
    documento_id: str | None = None,
    nome_arquivo: str | None = None,
) -> str:
    """Valida e resolve o caminho no bucket garantindo isolamento estrito de tenant."""
    t_id = validar_id(tenant_id, "tenant_id")

    if caminho:
        partes = caminho.strip("/").split("/")
        # Formato esperado: tenants/{t}/trabalhadores/{trab}/documentos/{doc}/{arquivo}
        if len(partes) != 7:
            raise CaminhoInvalidoError(f"Caminho estruturado incorretamente: {caminho!r}")
        if partes[0] != "tenants" or partes[2] != "trabalhadores" or partes[4] != "documentos":
            raise CaminhoInvalidoError(
                f"Caminho fora da hierarquia padrão da ADR 0006: {caminho!r}"
            )
        if partes[1] != t_id:
            raise CaminhoInvalidoError(
                f"Violação de isolamento multi-tenant: caminho '{caminho}' não pertence a '{t_id}'"
            )

        validar_id(partes[1], "tenant_id")
        validar_id(partes[3], "trabalhador_id")
        validar_id(partes[5], "documento_id")
        if not _ARQUIVO_REGEX.fullmatch(partes[6]):
            raise CaminhoInvalidoError(f"Nome de arquivo inválido no caminho: {partes[6]!r}")
        return caminho.strip("/")

    if trabalhador_id and documento_id and nome_arquivo:
        return construir_caminho(t_id, trabalhador_id, documento_id, nome_arquivo)

    raise CaminhoInvalidoError(
        "Informe 'caminho' completo ou o conjunto 'trabalhador_id', "
        "'documento_id' e 'nome_arquivo'."
    )


@runtime_checkable
class ArmazenamentoDocumentos(Protocol):
    """Porta para o backend de armazenamento de documentos isolado por tenant."""

    tenant_id: str

    def salvar(
        self,
        trabalhador_id: str,
        documento_id: str,
        conteudo: bytes,
        extensao: Literal["pdf", "jpg"],
        miniatura: bool = False,
        arquivo_uuid: str | None = None,
    ) -> str:
        """Salva um documento e retorna o caminho canônico persistido no bucket."""
        ...

    def obter_url_leitura(
        self,
        caminho: str | None = None,
        trabalhador_id: str | None = None,
        documento_id: str | None = None,
        nome_arquivo: str | None = None,
        expira_em_segundos: int = 300,
    ) -> str:
        """Retorna uma URL assinada/temporária para leitura/download do documento (teto 300s)."""
        ...

    def excluir(
        self,
        caminho: str | None = None,
        trabalhador_id: str | None = None,
        documento_id: str | None = None,
        nome_arquivo: str | None = None,
    ) -> None:
        """Exclui um documento do armazenamento de forma idempotente."""
        ...

    def saude(self) -> bool:
        """Verifica se o backend de armazenamento está acessível e operacional."""
        ...
