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
import uuid
from typing import Literal

from habilita.armazenamento.porta import (
    TETO_MAXIMO_EXPIRACAO_SEGUNDOS,
    ArmazenamentoDocumentos,
    ArmazenamentoError,
    CaminhoInvalidoError,
    ObjetoNaoEncontradoError,
    construir_caminho,
    validar_e_resolver_caminho,
    validar_id,
)


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Impede o redirecionamento automático para evitar vazamento de credenciais."""

    def redirect_request(  # type: ignore[override]
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        return None


class SupabaseArmazenamento(ArmazenamentoDocumentos):
    """Adapter concreto para persistência de documentos no Supabase Storage."""

    def __init__(
        self,
        tenant_id: str,
        base_url: str,
        service_key: str,
        bucket: str = "documentos",
        public_url: str | None = None,
        timeout_segundos: float = 5.0,
    ) -> None:
        """Inicializa o cliente do Supabase Storage vinculado ao tenant da claim."""
        self.tenant_id = validar_id(tenant_id, "tenant_id")
        self.base_url = base_url.rstrip("/")
        self.service_key = service_key
        self.bucket = bucket
        self.public_url = (public_url or base_url).rstrip("/")
        self.timeout = timeout_segundos
        # Opener sem redirects para evitar vazamento da chave de serviço
        self._opener = urllib.request.build_opener(NoRedirectHandler)

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
        url = f"{self.base_url}/object/{self.bucket}/{caminho}"

        req = urllib.request.Request(  # noqa: S310
            url,
            data=conteudo,
            headers={
                "Authorization": f"Bearer {self.service_key}",
                "Content-Type": content_type,
                "x-upsert": "false",
            },
            method="POST",
        )

        try:
            with self._opener.open(req, timeout=self.timeout) as resp:  # noqa: S310
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
        url = f"{self.base_url}/object/sign/{self.bucket}/{caminho_resolvido}"
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
            with self._opener.open(req, timeout=self.timeout) as resp:  # noqa: S310
                if resp.status != 200:
                    corpo = resp.read().decode("utf-8", errors="replace")
                    raise ArmazenamentoError(
                        f"Falha ao assinar URL no Supabase Storage: HTTP {resp.status} - {corpo}"
                    )
                try:
                    dados: dict[str, str] = json.loads(resp.read().decode("utf-8"))
                except json.JSONDecodeError as json_err:
                    raise ArmazenamentoError(
                        "Resposta do Storage não contém JSON válido."
                    ) from json_err

                signed_path = dados.get("signedURL", "")
                if not signed_path:
                    raise ArmazenamentoError("Supabase Storage não retornou campo 'signedURL'.")

                if signed_path.startswith("/"):
                    return f"{self.public_url}{signed_path}"
                return f"{self.public_url}/{signed_path}"

        except urllib.error.HTTPError as err:
            detalhe = err.read().decode("utf-8", errors="replace")
            if err.code == 404 or '"not_found"' in detalhe or '"statusCode":"404"' in detalhe:
                raise ObjetoNaoEncontradoError(
                    f"Documento não encontrado no Supabase Storage: {caminho_resolvido}"
                ) from err
            raise ArmazenamentoError(
                f"Erro HTTP {err.code} ao gerar URL assinada para {caminho_resolvido}: {detalhe}"
            ) from err
        except urllib.error.URLError as err:
            raise ArmazenamentoError(
                f"Erro de conexão com o Supabase Storage ao gerar URL assinada: {err.reason}"
            ) from err

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
        url = f"{self.base_url}/object/{self.bucket}/{caminho_resolvido}"

        req = urllib.request.Request(  # noqa: S310
            url,
            headers={"Authorization": f"Bearer {self.service_key}"},
            method="DELETE",
        )

        try:
            with self._opener.open(req, timeout=self.timeout) as resp:  # noqa: S310
                if resp.status not in (200, 204, 404):
                    corpo = resp.read().decode("utf-8", errors="replace")
                    raise ArmazenamentoError(
                        f"Falha ao excluir no Supabase Storage: HTTP {resp.status} - {corpo}"
                    )
        except urllib.error.HTTPError as err:
            # 404 na exclusão é idempotente (já não existe mais)
            if err.code != 404:
                detalhe = err.read().decode("utf-8", errors="replace")
                raise ArmazenamentoError(
                    f"Erro HTTP {err.code} ao excluir documento {caminho_resolvido}: {detalhe}"
                ) from err
        except urllib.error.URLError as err:
            raise ArmazenamentoError(
                f"Erro de conexão ao excluir documento {caminho_resolvido}: {err.reason}"
            ) from err

    def saude(self) -> bool:
        url = f"{self.base_url}/status"
        req = urllib.request.Request(url, method="GET")  # noqa: S310

        try:
            with self._opener.open(req, timeout=self.timeout) as resp:  # noqa: S310
                return bool(resp.status == 200)
        except Exception:
            return False
