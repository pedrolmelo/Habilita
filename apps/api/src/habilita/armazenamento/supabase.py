"""Adapter de armazenamento para o Supabase Storage via API REST.

Implementa a porta ArmazenamentoDocumentos comunicando-se diretamente
com o serviço de Storage do Supabase (local no Docker Compose ou na nuvem).
Utiliza a biblioteca padrão urllib para manter zero dependências extras em produção.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from habilita.armazenamento.porta import (
    ArmazenamentoDocumentos,
    ArmazenamentoError,
    ObjetoNaoEncontradoError,
    validar_caminho,
)


class SupabaseArmazenamento(ArmazenamentoDocumentos):
    """Adapter concreto para persistência de documentos no Supabase Storage."""

    def __init__(
        self,
        base_url: str,
        service_key: str,
        bucket: str = "documentos",
        public_url: str | None = None,
        timeout_segundos: float = 5.0,
    ) -> None:
        """Inicializa o cliente do Supabase Storage.

        Args:
            base_url: URL base do serviço de Storage (ex: 'http://storage:5000').
            service_key: Chave de serviço (SUPABASE_SERVICE_KEY) para operações administrativas.
            bucket: Nome do bucket privado (padrão: 'documentos').
            public_url: URL base que os navegadores/clientes usam para acessar (ex: 'http://127.0.0.1:5000').
                        Se omitido, assume o mesmo valor de base_url.
            timeout_segundos: Timeout máximo para chamadas HTTP em segundos.
        """
        self.base_url = base_url.rstrip("/")
        self.service_key = service_key
        self.bucket = bucket
        self.public_url = (public_url or base_url).rstrip("/")
        self.timeout = timeout_segundos

    def salvar(self, tenant_id: str, documento_id: str, conteudo: bytes, content_type: str) -> str:
        caminho = validar_caminho(tenant_id, documento_id)
        url = f"{self.base_url}/object/{self.bucket}/{caminho}"

        req = urllib.request.Request(  # noqa: S310
            url,
            data=conteudo,
            headers={
                "Authorization": f"Bearer {self.service_key}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                if resp.status not in (200, 201):
                    corpo = resp.read().decode("utf-8", errors="replace")
                    msg = f"Falha no Supabase Storage: HTTP {resp.status} - {corpo}"
                    raise ArmazenamentoError(msg)
                return caminho
        except urllib.error.HTTPError as err:
            detalhe = err.read().decode("utf-8", errors="replace")
            raise ArmazenamentoError(
                f"Erro HTTP {err.code} ao salvar documento {caminho}: {detalhe}"
            ) from err
        except urllib.error.URLError as err:
            raise ArmazenamentoError(
                f"Erro de conexão ao salvar documento {caminho} no Supabase Storage: {err.reason}"
            ) from err

    def obter_url_leitura(
        self, tenant_id: str, documento_id: str, expira_em_segundos: int = 900
    ) -> str:
        caminho = validar_caminho(tenant_id, documento_id)
        url = f"{self.base_url}/object/sign/{self.bucket}/{caminho}"
        payload = json.dumps({"expiresIn": expira_em_segundos}).encode("utf-8")

        req = urllib.request.Request(  # noqa: S310
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.service_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                if resp.status != 200:
                    corpo = resp.read().decode("utf-8", errors="replace")
                    raise ArmazenamentoError(
                        f"Falha ao assinar URL no Supabase Storage: HTTP {resp.status} - {corpo}"
                    )
                dados: dict[str, str] = json.loads(resp.read().decode("utf-8"))
                signed_path = dados.get("signedURL", "")
                if not signed_path:
                    raise ArmazenamentoError("Supabase Storage não retornou campo 'signedURL'.")

                if signed_path.startswith("/"):
                    return f"{self.public_url}{signed_path}"
                return f"{self.public_url}/{signed_path}"

        except urllib.error.HTTPError as err:
            detalhe = err.read().decode("utf-8", errors="replace")
            # Supabase Storage pode retornar 404 ou 400 com erro not_found no corpo
            if err.code == 404 or '"not_found"' in detalhe or '"statusCode":"404"' in detalhe:
                raise ObjetoNaoEncontradoError(
                    f"Documento não encontrado no Supabase Storage: {caminho}"
                ) from err
            raise ArmazenamentoError(
                f"Erro HTTP {err.code} ao gerar URL assinada para {caminho}: {detalhe}"
            ) from err
        except urllib.error.URLError as err:
            raise ArmazenamentoError(
                f"Erro de conexão com o Supabase Storage ao gerar URL assinada: {err.reason}"
            ) from err

    def excluir(self, tenant_id: str, documento_id: str) -> None:
        caminho = validar_caminho(tenant_id, documento_id)
        url = f"{self.base_url}/object/{self.bucket}/{caminho}"

        req = urllib.request.Request(  # noqa: S310
            url,
            headers={
                "Authorization": f"Bearer {self.service_key}",
            },
            method="DELETE",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                if resp.status not in (200, 204, 404):
                    corpo = resp.read().decode("utf-8", errors="replace")
                    raise ArmazenamentoError(
                        f"Falha ao excluir no Supabase Storage: HTTP {resp.status} - {corpo}"
                    )
        except urllib.error.HTTPError as err:
            # 404 na exclusão é idempotente (já não existe)
            if err.code != 404:
                detalhe = err.read().decode("utf-8", errors="replace")
                raise ArmazenamentoError(
                    f"Erro HTTP {err.code} ao excluir documento {caminho}: {detalhe}"
                ) from err
        except urllib.error.URLError as err:
            raise ArmazenamentoError(
                f"Erro de conexão ao excluir documento {caminho} do Supabase Storage: {err.reason}"
            ) from err

    def saude(self) -> bool:
        url = f"{self.base_url}/status"
        req = urllib.request.Request(url, method="GET")  # noqa: S310

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                return bool(resp.status == 200)
        except Exception:
            return False
