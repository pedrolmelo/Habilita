"""Implementação em memória da porta ArmazenamentoDocumentos para uso em testes.

Útil para testes unitários rápidos e isolados, sem dependência de serviços externos
ou contêineres Docker em execução.
"""

from __future__ import annotations

import uuid
from typing import Literal

from habilita.armazenamento.porta import (
    TETO_MAXIMO_EXPIRACAO_SEGUNDOS,
    ArmazenamentoDocumentos,
    CaminhoInvalidoError,
    ObjetoNaoEncontradoError,
    construir_caminho,
    validar_e_resolver_caminho,
    validar_id,
)


class MemoriaArmazenamento(ArmazenamentoDocumentos):
    """Adapter em memória para armazenamento de documentos durante testes."""

    def __init__(self, tenant_id: str, public_url: str = "http://storage.local.test") -> None:
        self.tenant_id = validar_id(tenant_id, "tenant_id")
        self.public_url = public_url.rstrip("/")
        # Mapeia caminho canônico relativo -> (conteúdo binário, tipo mime)
        self._arquivos: dict[str, tuple[bytes, str]] = {}
        self._esta_saudavel: bool = True

    def salvar(
        self,
        trabalhador_id: str,
        documento_id: str,
        conteudo: bytes,
        extensao: Literal["pdf", "jpg"],
        miniatura: bool = False,
        arquivo_uuid: str | None = None,
    ) -> str:
        if extensao not in ("pdf", "jpg"):
            raise CaminhoInvalidoError(
                f"Extensão não permitida: '{extensao}'. Permitidas: 'pdf', 'jpg'."
            )

        uid = arquivo_uuid or str(uuid.uuid4())
        nome_arquivo = f"{uid}_mini.jpg" if miniatura else f"{uid}.{extensao}"
        caminho = construir_caminho(self.tenant_id, trabalhador_id, documento_id, nome_arquivo)

        content_type = "image/jpeg" if (miniatura or extensao == "jpg") else "application/pdf"
        self._arquivos[caminho] = (conteudo, content_type)
        return caminho

    def obter_url_leitura(
        self,
        caminho: str | None = None,
        trabalhador_id: str | None = None,
        documento_id: str | None = None,
        nome_arquivo: str | None = None,
        expira_em_segundos: int = 300,
    ) -> str:
        if expira_em_segundos <= 0 or expira_em_segundos > TETO_MAXIMO_EXPIRACAO_SEGUNDOS:
            raise ValueError(
                f"Tempo de expiração deve ser entre 1 e {TETO_MAXIMO_EXPIRACAO_SEGUNDOS} segundos."
            )

        caminho_resolvido = validar_e_resolver_caminho(
            self.tenant_id, caminho, trabalhador_id, documento_id, nome_arquivo
        )
        if caminho_resolvido not in self._arquivos:
            raise ObjetoNaoEncontradoError(f"Documento não encontrado: {caminho_resolvido}")
        return f"{self.public_url}/mock-signed/{caminho_resolvido}?exp={expira_em_segundos}"

    def excluir(
        self,
        caminho: str | None = None,
        trabalhador_id: str | None = None,
        documento_id: str | None = None,
        nome_arquivo: str | None = None,
    ) -> None:
        caminho_resolvido = validar_e_resolver_caminho(
            self.tenant_id, caminho, trabalhador_id, documento_id, nome_arquivo
        )
        self._arquivos.pop(caminho_resolvido, None)

    def saude(self) -> bool:
        return self._esta_saudavel

    def definir_saude(self, saudavel: bool) -> None:
        """Auxiliar de teste para simular falhas de saúde no serviço."""
        self._esta_saudavel = saudavel

    def obter_conteudo(
        self,
        caminho: str | None = None,
        trabalhador_id: str | None = None,
        documento_id: str | None = None,
        nome_arquivo: str | None = None,
    ) -> tuple[bytes, str] | None:
        """Auxiliar de teste para inspecionar conteúdo gravado em memória."""
        caminho_resolvido = validar_e_resolver_caminho(
            self.tenant_id, caminho, trabalhador_id, documento_id, nome_arquivo
        )
        return self._arquivos.get(caminho_resolvido)
