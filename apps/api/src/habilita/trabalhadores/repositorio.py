"""Repositório de dados para Trabalhadores e Documentos (J2 e J3).

Conforme a ADR 0002 e AGENTS.md:
- Escopo restrito ao tenantId injetado no construtor.
- Controle de acesso intra-tenant para terceirizadas.
- Integração determinística compatível com o seed.
"""

from __future__ import annotations

import datetime
import hashlib
import uuid
from typing import Any

from habilita.trabalhadores.schemas import (
    Alocacao,
    ArquivoMetadados,
    Documento,
    Trabalhador,
    TrabalhadorDetalhe,
    UrlDownloadResponse,
)

# Base determinística em memória compatível com o seed
_BANCO_TRABALHADORES: dict[str, dict[str, dict[str, Any]]] = {
    "tnt_alfa": {
        "trb_alfa_1": {
            "id": "trb_alfa_1",
            "terceirizadaId": "ter_alfa_1",
            "nome": "Carlos Eduardo Silva",
            "cpfMascarado": "***.000.001-**",
            "cpf": "10100000126",
            "ativo": True,
            "alocacoes": ["ctr_alfa_1"],
        },
        "trb_alfa_y1": {
            "id": "trb_alfa_y1",
            "terceirizadaId": "ter_alfa_2",
            "nome": "Yuri Ramos",
            "cpfMascarado": "***.000.002-**",
            "cpf": "10100000207",
            "ativo": True,
            "alocacoes": [],
        },
    },
    "tnt_beta": {
        "trb_beta_1": {
            "id": "trb_beta_1",
            "terceirizadaId": "ter_beta_1",
            "nome": "Alexandre Pires Barbosa",
            "cpfMascarado": "***.000.001-**",
            "cpf": "20200000160",
            "ativo": True,
            "alocacoes": ["ctr_beta_1"],
        }
    },
}

_BANCO_DOCUMENTOS: dict[str, dict[str, dict[str, Any]]] = {
    "tnt_alfa": {
        "doc_alfa_1_aso": {
            "id": "doc_alfa_1_aso",
            "trabalhadorId": "trb_alfa_1",
            "tipoDocumentoId": "tip_aso",
            "validoAte": "2027-01-01",
            "statusRevisao": "APROVADO",
            "enviadoEm": "2026-10-15T10:00:00Z",
            "dataEmissao": "2026-01-01",
            "revisadoEm": "2026-10-16T14:00:00Z",
            "motivoRejeicao": None,
            "situacaoValidade": "VALIDO",
            "arquivo": {
                "contentType": "application/pdf",
                "tamanhoBytes": 1024,
                "sha256": hashlib.sha256(b"conteudo-ficticio-alfa-1").hexdigest(),
            },
        }
    },
    "tnt_beta": {
        "doc_beta_1_aso": {
            "id": "doc_beta_1_aso",
            "trabalhadorId": "trb_beta_1",
            "tipoDocumentoId": "tip_aso",
            "validoAte": "2027-02-01",
            "statusRevisao": "PENDENTE",
            "enviadoEm": "2026-10-16T11:00:00Z",
            "dataEmissao": "2026-02-01",
            "revisadoEm": None,
            "motivoRejeicao": None,
            "situacaoValidade": "VALIDO",
            "arquivo": {
                "contentType": "application/pdf",
                "tamanhoBytes": 2048,
                "sha256": hashlib.sha256(b"conteudo-ficticio-beta-1").hexdigest(),
            },
        }
    },
}


class TrabalhadoresRepositorio:
    """Repositório isolado por tenant."""

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id

    # -------------------------------------------------------------------------
    # Trabalhadores
    # -------------------------------------------------------------------------
    def listar_trabalhadores(
        self,
        terceirizada_id_filtro: str | None = None,
        limite: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Trabalhador], str | None]:
        tenant_map = _BANCO_TRABALHADORES.setdefault(self.tenant_id, {})
        todos = sorted(tenant_map.values(), key=lambda t: t["id"])

        if terceirizada_id_filtro:
            todos = [t for t in todos if t["terceirizadaId"] == terceirizada_id_filtro]

        inicio = 0
        if cursor:
            for i, item in enumerate(todos):
                if item["id"] == cursor:
                    inicio = i + 1
                    break

        itens_fatia = todos[inicio : inicio + limite]
        proximo_cursor = itens_fatia[-1]["id"] if inicio + limite < len(todos) else None

        resultado = [
            Trabalhador(
                id=t["id"],
                terceirizadaId=t["terceirizadaId"],
                nome=t["nome"],
                cpfMascarado=t["cpfMascarado"],
                ativo=t["ativo"],
            )
            for t in itens_fatia
        ]
        return resultado, proximo_cursor

    def obter_trabalhador(
        self, trabalhador_id: str, terceirizada_id_filtro: str | None = None
    ) -> TrabalhadorDetalhe | None:
        tenant_map = _BANCO_TRABALHADORES.get(self.tenant_id, {})
        dados = tenant_map.get(trabalhador_id)
        if not dados:
            return None
        if terceirizada_id_filtro and dados["terceirizadaId"] != terceirizada_id_filtro:
            return None

        # Documentos do trabalhador
        docs_map = _BANCO_DOCUMENTOS.get(self.tenant_id, {})
        docs_trb = [
            Documento(**d) for d in docs_map.values() if d.get("trabalhadorId") == trabalhador_id
        ]

        # Alocações do trabalhador
        alocs_trb = [
            Alocacao(
                contratoId=ctr_id,
                trabalhadorId=trabalhador_id,
                semaforo="VERDE",
                pendencias=[],
                calculadoEm="2026-10-23T00:00:00Z",
            )
            for ctr_id in dados.get("alocacoes", [])
        ]

        return TrabalhadorDetalhe(
            id=dados["id"],
            terceirizadaId=dados["terceirizadaId"],
            nome=dados["nome"],
            cpfMascarado=dados["cpfMascarado"],
            ativo=dados["ativo"],
            documentos=docs_trb,
            alocacoes=alocs_trb,
        )

    def criar_trabalhador(self, nome: str, cpf: str, terceirizada_id: str) -> Trabalhador:
        tenant_map = _BANCO_TRABALHADORES.setdefault(self.tenant_id, {})
        trb_id = f"trb_{uuid.uuid4().hex[:8]}"
        cpf_limpo = cpf.replace(".", "").replace("-", "")
        cpf_mascarado = f"***.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-**"

        registro = {
            "id": trb_id,
            "terceirizadaId": terceirizada_id,
            "nome": nome,
            "cpf": cpf_limpo,
            "cpfMascarado": cpf_mascarado,
            "ativo": True,
            "alocacoes": [],
        }
        tenant_map[trb_id] = registro
        return Trabalhador(
            id=trb_id,
            terceirizadaId=terceirizada_id,
            nome=nome,
            cpfMascarado=cpf_mascarado,
            ativo=True,
        )

    def vincular_alocacao(self, contrato_id: str, trabalhador_id: str) -> Alocacao:
        tenant_map = _BANCO_TRABALHADORES.setdefault(self.tenant_id, {})
        trb = tenant_map.get(trabalhador_id)
        if trb and contrato_id not in trb.get("alocacoes", []):
            trb.setdefault("alocacoes", []).append(contrato_id)

        agora = datetime.datetime.now(datetime.UTC).isoformat()
        return Alocacao(
            contratoId=contrato_id,
            trabalhadorId=trabalhador_id,
            semaforo="VERDE",
            pendencias=[],
            calculadoEm=agora,
        )

    # -------------------------------------------------------------------------
    # Documentos
    # -------------------------------------------------------------------------
    def listar_documentos(
        self,
        status_revisao: str | None = None,
        terceirizada_id_filtro: str | None = None,
        limite: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Documento], str | None]:
        docs_map = _BANCO_DOCUMENTOS.setdefault(self.tenant_id, {})
        todos = sorted(docs_map.values(), key=lambda d: d["id"])

        if status_revisao:
            todos = [d for d in todos if d.get("statusRevisao") == status_revisao]

        if terceirizada_id_filtro:
            trb_map = _BANCO_TRABALHADORES.get(self.tenant_id, {})
            trb_ids_terc = {
                tid
                for tid, trb in trb_map.items()
                if trb["terceirizadaId"] == terceirizada_id_filtro
            }
            todos = [d for d in todos if d.get("trabalhadorId") in trb_ids_terc]

        inicio = 0
        if cursor:
            for i, item in enumerate(todos):
                if item["id"] == cursor:
                    inicio = i + 1
                    break

        itens_fatia = todos[inicio : inicio + limite]
        proximo_cursor = itens_fatia[-1]["id"] if inicio + limite < len(todos) else None

        resultado = [Documento(**d) for d in itens_fatia]
        return resultado, proximo_cursor

    def obter_documento(
        self, documento_id: str, terceirizada_id_filtro: str | None = None
    ) -> Documento | None:
        docs_map = _BANCO_DOCUMENTOS.get(self.tenant_id, {})
        dados = docs_map.get(documento_id)
        if not dados:
            return None

        if terceirizada_id_filtro:
            trb_map = _BANCO_TRABALHADORES.get(self.tenant_id, {})
            trb = trb_map.get(dados.get("trabalhadorId", ""))
            if not trb or trb.get("terceirizadaId") != terceirizada_id_filtro:
                return None

        return Documento(**dados)

    def criar_documento(
        self,
        trabalhador_id: str,
        tipo_documento_id: str,
        valido_ate: str,
        data_emissao: str | None,
        arquivo_meta: ArquivoMetadados,
    ) -> Documento:
        docs_map = _BANCO_DOCUMENTOS.setdefault(self.tenant_id, {})
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        agora = datetime.datetime.now(datetime.UTC).isoformat()

        registro = {
            "id": doc_id,
            "trabalhadorId": trabalhador_id,
            "tipoDocumentoId": tipo_documento_id,
            "validoAte": valido_ate,
            "statusRevisao": "PENDENTE",
            "enviadoEm": agora,
            "dataEmissao": data_emissao,
            "revisadoEm": None,
            "motivoRejeicao": None,
            "situacaoValidade": "VALIDO",
            "arquivo": arquivo_meta.model_dump(),
        }
        docs_map[doc_id] = registro
        return Documento(**registro)

    def aprovar_documento(self, documento_id: str) -> Documento | None:
        docs_map = _BANCO_DOCUMENTOS.get(self.tenant_id, {})
        dados = docs_map.get(documento_id)
        if not dados:
            return None

        dados["statusRevisao"] = "APROVADO"
        dados["revisadoEm"] = datetime.datetime.now(datetime.UTC).isoformat()
        dados["motivoRejeicao"] = None
        return Documento(**dados)

    def rejeitar_documento(self, documento_id: str, motivo: str) -> Documento | None:
        docs_map = _BANCO_DOCUMENTOS.get(self.tenant_id, {})
        dados = docs_map.get(documento_id)
        if not dados:
            return None

        dados["statusRevisao"] = "REJEITADO"
        dados["revisadoEm"] = datetime.datetime.now(datetime.UTC).isoformat()
        dados["motivoRejeicao"] = motivo
        return Documento(**dados)

    def gerar_url_download(
        self, documento_id: str, terceirizada_id_filtro: str | None = None
    ) -> UrlDownloadResponse | None:
        doc = self.obter_documento(documento_id, terceirizada_id_filtro)
        if not doc:
            return None

        expira = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=15)).isoformat()
        url = f"http://127.0.0.1:9199/download/storage/v1/b/demo-habilita.appspot.com/o/tenants%2F{self.tenant_id}%2Fdocumentos%2F{documento_id}.pdf?alt=media"
        return UrlDownloadResponse(url=url, expiraEm=expira)
