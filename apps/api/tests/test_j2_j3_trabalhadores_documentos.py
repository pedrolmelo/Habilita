"""Testes de integração para as Jornadas J2 e J3 (Trabalhadores e Documentos).

Cobre:
- J2: Cadastro de trabalhador, máscara de CPF, vínculo com contrato (alocação)
- J2: Upload de documentos com validação por assinatura mágica de bytes (PDF/JPEG/PNG)
- J3: Fila de revisão de documentos do Gestor
- J3: Geração de URL temporária de download
- J3: Aprovação e rejeição com motivo obrigatório
- Segurança: Isolamento de tenant e permissões por papel (403 e 404 Problem Details)
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from .conftest import (
    CTR_ALFA_1,
    DOC_ALFA_1_ASO,
    DOC_BETA_1_ASO,
    TER_ALFA_1,
    TRB_ALFA_1,
    TRB_ALFA_Y1,
    TRB_BETA_1,
)


def test_j2_cadastrar_e_listar_trabalhador(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Valida cadastro de trabalhador, máscara de CPF e visibilidade por terceirizada."""
    payload = {
        "nome": "Marcos Vinicius Santos",
        "cpf": "123.456.789-01",
        "terceirizadaId": TER_ALFA_1,
    }
    resp_post = client.post("/trabalhadores", json=payload, headers=headers_gestor_alfa)
    assert resp_post.status_code == 201
    trb = resp_post.json()
    assert trb["nome"] == payload["nome"]
    assert trb["cpfMascarado"] == "***.456.789-**"
    assert trb["terceirizadaId"] == TER_ALFA_1
    assert "id" in trb

    # Terceirizada 1 lista e enxerga seu trabalhador
    resp_get = client.get("/trabalhadores", headers=headers_terceirizada_1_alfa)
    assert resp_get.status_code == 200
    itens = resp_get.json()["itens"]
    assert any(t["id"] == trb["id"] for t in itens)


def test_j2_vincular_trabalhador_ao_contrato(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """Valida alocação de trabalhador em contrato existente."""
    payload = {"trabalhadorId": TRB_ALFA_1}
    resp = client.post(
        f"/contratos/{CTR_ALFA_1}/alocacoes",
        json=payload,
        headers=headers_gestor_alfa,
    )
    assert resp.status_code == 201
    aloc = resp.json()
    assert aloc["contratoId"] == CTR_ALFA_1
    assert aloc["trabalhadorId"] == TRB_ALFA_1
    assert aloc["semaforo"] in ("VERDE", "AMARELO", "VERMELHO")


def test_j2_upload_documento_pdf_valido(
    client: TestClient,
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Valida envio de PDF com assinatura mágica correta e metadados."""
    pdf_conteudo = b"%PDF-1.4 ficticio de teste de SST para upload no emulador"
    arquivos = {"arquivo": ("aso_exame.pdf", io.BytesIO(pdf_conteudo), "application/pdf")}
    dados = {
        "tipoDocumentoId": "tip_aso",
        "validoAte": "2027-06-30",
        "dataEmissao": "2026-06-30",
    }
    resp = client.post(
        f"/trabalhadores/{TRB_ALFA_1}/documentos",
        files=arquivos,
        data=dados,
        headers=headers_terceirizada_1_alfa,
    )
    assert resp.status_code == 201
    doc = resp.json()
    assert doc["trabalhadorId"] == TRB_ALFA_1
    assert doc["tipoDocumentoId"] == "tip_aso"
    assert doc["statusRevisao"] == "PENDENTE"
    assert doc["arquivo"]["contentType"] == "application/pdf"
    assert doc["arquivo"]["tamanhoBytes"] == len(pdf_conteudo)


def test_j2_upload_rejeita_arquivo_invalido_sem_assinatura_magica(
    client: TestClient,
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Arquivos que não são PDF, JPEG ou PNG são rejeitados com 400 Problem Details."""
    conteudo_falso = b"texto simples sem assinatura de PDF ou imagem"
    arquivos = {"arquivo": ("virus.exe", io.BytesIO(conteudo_falso), "application/octet-stream")}
    dados = {
        "tipoDocumentoId": "tip_aso",
        "validoAte": "2027-01-01",
    }
    resp = client.post(
        f"/trabalhadores/{TRB_ALFA_1}/documentos",
        files=arquivos,
        data=dados,
        headers=headers_terceirizada_1_alfa,
    )
    assert resp.status_code == 400
    assert "application/problem+json" in resp.headers.get("content-type", "")
    assert resp.json().get("status") == 400


def test_j3_gestor_revisa_fila_e_gera_url_download(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """Gestor consulta documentos e obtém URL assinada para visualização."""
    resp_lista = client.get("/documentos", headers=headers_gestor_alfa)
    assert resp_lista.status_code == 200
    assert "itens" in resp_lista.json()

    # Gera link de download para o documento existente no seed
    resp_url = client.post(
        f"/documentos/{DOC_ALFA_1_ASO}/url-download",
        headers=headers_gestor_alfa,
    )
    assert resp_url.status_code == 200
    dados_url = resp_url.json()
    assert "url" in dados_url
    assert "expiraEm" in dados_url


def test_j3_gestor_aprova_e_rejeita_documento(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """Valida transição de estado de documento aprovado e rejeitado com motivo."""
    # Aprovação
    resp_aprov = client.post(
        f"/documentos/{DOC_ALFA_1_ASO}/aprovacao",
        headers=headers_gestor_alfa,
    )
    assert resp_aprov.status_code == 200
    assert resp_aprov.json()["statusRevisao"] == "APROVADO"

    # Rejeição com motivo obrigatório
    motivo_payload = {"motivo": "CRM do médico emissor ilegível no carimbo da página 2."}
    resp_rej = client.post(
        f"/documentos/{DOC_ALFA_1_ASO}/rejeicao",
        json=motivo_payload,
        headers=headers_gestor_alfa,
    )
    assert resp_rej.status_code == 200
    doc_rej = resp_rej.json()
    assert doc_rej["statusRevisao"] == "REJEITADO"
    assert doc_rej["motivoRejeicao"] == motivo_payload["motivo"]


def test_j3_terceirizada_nao_pode_aprovar_documento_retorna_403(
    client: TestClient,
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Papel terceirizada é proibido de aprovar documentos (apenas Gestor)."""
    resp = client.post(
        f"/documentos/{DOC_ALFA_1_ASO}/aprovacao",
        headers=headers_terceirizada_1_alfa,
    )
    assert resp.status_code == 403
    assert "application/problem+json" in resp.headers.get("content-type", "")


def test_j2_isolamento_horizontal_trabalhador_e_documento_outro_tenant_retorna_404(
    client: TestClient,
    headers_gestor_alfa: dict[str, str],
) -> None:
    """Gestor de Alfa acessa trabalhador e documento de Beta -> 404 Problem Details."""
    resp_trb = client.get(f"/trabalhadores/{TRB_BETA_1}", headers=headers_gestor_alfa)
    assert resp_trb.status_code == 404
    assert "application/problem+json" in resp_trb.headers.get("content-type", "")

    resp_doc = client.get(f"/documentos/{DOC_BETA_1_ASO}", headers=headers_gestor_alfa)
    assert resp_doc.status_code == 404
    assert "application/problem+json" in resp_doc.headers.get("content-type", "")


def test_j2_isolamento_intra_tenant_terceirizada_distinta_retorna_404(
    client: TestClient,
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Terceirizada 1 acessa trabalhador da Terceirizada 2 -> 404 Problem Details."""
    resp = client.get(
        f"/trabalhadores/{TRB_ALFA_Y1}",
        headers=headers_terceirizada_1_alfa,
    )
    assert resp.status_code == 404
    assert "application/problem+json" in resp.headers.get("content-type", "")
