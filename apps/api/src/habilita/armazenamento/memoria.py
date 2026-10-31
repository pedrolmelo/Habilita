"""Implementação em memória da porta ArmazenamentoDocumentos.

Útil para testes unitários rápidos e isolados, sem dependência de serviços externos
ou contêineres Docker em execução.
"""

from __future__ import annotations

from habilita.armazenamento.porta import (
    ArmazenamentoDocumentos,
    ObjetoNaoEncontradoError,
    validar_caminho,
)


class MemoriaArmazenamento(ArmazenamentoDocumentos):
    """Adapter em memória para armazenamento de documentos durante testes."""

    def __init__(self, public_url: str = "http://storage.local.test") -> None:
        self.public_url = public_url.rstrip("/")
        # Mapeia caminho relativo -> (conteúdo binário, tipo mime)
        self._arquivos: dict[str, tuple[bytes, str]] = {}
        self._esta_saudavel: bool = True

    def salvar(self, tenant_id: str, documento_id: str, conteudo: bytes, content_type: str) -> str:
        caminho = validar_caminho(tenant_id, documento_id)
        self._arquivos[caminho] = (conteudo, content_type)
        return caminho

    def obter_url_leitura(
        self, tenant_id: str, documento_id: str, expira_em_segundos: int = 900
    ) -> str:
        caminho = validar_caminho(tenant_id, documento_id)
        if caminho not in self._arquivos:
            raise ObjetoNaoEncontradoError(f"Documento não encontrado: {caminho}")
        return f"{self.public_url}/mock-signed/{caminho}?exp={expira_em_segundos}"

    def excluir(self, tenant_id: str, documento_id: str) -> None:
        caminho = validar_caminho(tenant_id, documento_id)
        self._arquivos.pop(caminho, None)

    def saude(self) -> bool:
        return self._esta_saudavel

    def definir_saude(self, saudavel: bool) -> None:
        """Auxiliar de teste para simular falhas de saúde no serviço."""
        self._esta_saudavel = saudavel

    def obter_conteudo(self, tenant_id: str, documento_id: str) -> tuple[bytes, str] | None:
        """Auxiliar de teste para inspecionar conteúdo gravado em memória."""
        caminho = validar_caminho(tenant_id, documento_id)
        return self._arquivos.get(caminho)
