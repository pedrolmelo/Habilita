"""Porta e contratos para o serviço de armazenamento de documentos.

Define a interface abstrata (Protocol) que a aplicação utiliza para persistir,
ler e excluir arquivos de documentos de SST, sem acoplamento a provedores específicos.
Também centraliza a validação de caminhos e proteção contra path traversal.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

# Padrão seguro para tenant_id: apenas alfanuméricos, hífen e sublinhado (ex: tnt_alfa, tnt-123)
_TENANT_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")

# Padrão seguro para documento_id: alfanuméricos, hífen, sublinhado e ponto simples para extensão
_DOCUMENTO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9]+)?$")


class ArmazenamentoError(Exception):
    """Exceção base para operações de armazenamento."""


class CaminhoInvalidoError(ArmazenamentoError):
    """Lançada quando identificador contém caracteres inválidos ou path traversal."""


class ObjetoNaoEncontradoError(ArmazenamentoError):
    """Lançada quando o documento solicitado não existe no armazenamento."""


def validar_caminho(tenant_id: str, documento_id: str) -> str:
    """Valida identificadores e constrói o caminho isolado por tenant.

    Garante que o caminho gerado siga rigorosamente o padrão:
        tenants/{tenant_id}/documentos/{documento_id}

    Rejeita tentativas de path traversal (ex: '../', caminhos absolutos) e
    caracteres que fujam da convenção estrita.

    Args:
        tenant_id: Identificador do tenant (ex: 'tnt_alfa').
        documento_id: Identificador do documento (ex: 'doc_123' ou 'doc_123.pdf').

    Returns:
        Caminho relativo padronizado no bucket.

    Raises:
        CaminhoInvalidoError: Se tenant_id ou documento_id forem inválidos.
    """
    if not tenant_id or not isinstance(tenant_id, str):
        raise CaminhoInvalidoError("tenant_id não pode ser vazio ou nulo.")

    if not documento_id or not isinstance(documento_id, str):
        raise CaminhoInvalidoError("documento_id não pode ser vazio ou nulo.")

    # Verificações estritas contra path traversal
    if ".." in tenant_id or "/" in tenant_id or "\\" in tenant_id:
        msg = f"tenant_id inválido ou contém caracteres proibidos: {tenant_id!r}"
        raise CaminhoInvalidoError(msg)

    if ".." in documento_id or "/" in documento_id or "\\" in documento_id:
        msg = f"documento_id inválido ou contém caracteres proibidos: {documento_id!r}"
        raise CaminhoInvalidoError(msg)

    if not _TENANT_ID_REGEX.match(tenant_id):
        padrao = _TENANT_ID_REGEX.pattern
        raise CaminhoInvalidoError(
            f"tenant_id contém caracteres não permitidos. Esperado regex {padrao}."
        )

    if not _DOCUMENTO_ID_REGEX.match(documento_id):
        padrao = _DOCUMENTO_ID_REGEX.pattern
        raise CaminhoInvalidoError(
            f"documento_id contém caracteres não permitidos. Esperado regex {padrao}."
        )

    return f"tenants/{tenant_id}/documentos/{documento_id}"


@runtime_checkable
class ArmazenamentoDocumentos(Protocol):
    """Porta para o backend de armazenamento de documentos."""

    def salvar(self, tenant_id: str, documento_id: str, conteudo: bytes, content_type: str) -> str:
        """Salva um documento no armazenamento e retorna seu caminho relativo no bucket.

        Args:
            tenant_id: Identificador do tenant proprietário.
            documento_id: Identificador do documento.
            conteudo: Bytes do arquivo a ser salvo.
            content_type: Tipo MIME do arquivo (ex: 'application/pdf').

        Returns:
            Caminho relativo persistido (ex: 'tenants/{tenant_id}/documentos/{documento_id}').

        Raises:
            CaminhoInvalidoError: Se tenant_id ou documento_id violarem isolamento.
            ArmazenamentoError: Se a persistência falhar no backend.
        """
        ...

    def obter_url_leitura(
        self, tenant_id: str, documento_id: str, expira_em_segundos: int = 900
    ) -> str:
        """Retorna uma URL assinada/temporária para leitura/download do documento.

        Args:
            tenant_id: Identificador do tenant proprietário.
            documento_id: Identificador do documento.
            expira_em_segundos: Tempo de validade do link (padrão: 15 minutos / 900s).

        Returns:
            URL pública e assinada com token de acesso temporário.

        Raises:
            CaminhoInvalidoError: Se tenant_id ou documento_id forem inválidos.
            ObjetoNaoEncontradoError: Se o documento não for encontrado.
            ArmazenamentoError: Se houver falha ao gerar o link.
        """
        ...

    def excluir(self, tenant_id: str, documento_id: str) -> None:
        """Exclui um documento do armazenamento.

        Args:
            tenant_id: Identificador do tenant proprietário.
            documento_id: Identificador do documento.

        Raises:
            CaminhoInvalidoError: Se tenant_id ou documento_id forem inválidos.
            ArmazenamentoError: Se houver falha ao excluir o documento.
        """
        ...

    def saude(self) -> bool:
        """Verifica se o backend de armazenamento está acessível e operacional.

        Returns:
            True se o serviço responder com sucesso, False caso contrário.
        """
        ...
