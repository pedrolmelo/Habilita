"""Testes de integração para as Jornadas J2 e J3 (Trabalhadores e Documentos).

Cobre:
- H02.CA1: Cadastro de trabalhador com CPF válido, máscara e listagem
- H02.CA2: Alocação de trabalhador em contrato existente
- H02.CA3: Upload de PDF válido com assinatura de bytes e metadados
- H02.CA4: Upload rejeita tipo de mídia não suportado com 415
- H02.CA5: Upload acima de 5.000.000 bytes rejeitado com 413
- H02.CA6: CPF com dígitos verificadores inválidos rejeitado com 422
- H02.CA7: Tentativa de cadastrar CPF duplicado no mesmo tenant retorna 409
- H02.CA8: Alocação em contrato inexistente retorna 404
- H02.CA9: Upload com tipoDocumentoId inexistente no tenant retorna 404
- H03.CA1: Analista consulta fila de revisão e gera URL assinada de download
- H03.CA2: Analista aprova e rejeita documento com justificativa válida
- H03.CA3: Terceirizada proibida de aprovar documento (403)
- H03.CA4: Tentativa de aprovar documento que não está PENDENTE retorna 409
- H03.CA5: Rejeição com motivo menor que 10 caracteres retorna 422
- H03.CA6: Isolamento horizontal de trabalhador e documento de outro tenant (404)
- H03.CA7: Isolamento intra-tenant de trabalhador para terceirizada distinta (404)
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from .conftest import (
    CPF_TRB_ALFA_1,
    CTR_ALFA_1,
    DOC_ALFA_1_ASO,
    DOC_BETA_1_ASO,
    TER_ALFA_1,
    TRB_ALFA_1,
    TRB_ALFA_Y1,
    TRB_BETA_1,
)


def test_h02_ca1_cadastrar_e_listar_trabalhador(
    client: TestClient,
    headers_admin_alfa: dict[str, str],
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Valida cadastro de trabalhador com CPF válido, máscara e visibilidade por terceirizada."""
    payload = {
        "nome": "Marcos Vinicius Santos",
        "cpf": "529.982.247-25",
        "terceirizadaId": TER_ALFA_1,
    }
    resp_post = client.post("/trabalhadores", json=payload, headers=headers_admin_alfa)
    assert resp_post.status_code == 201
    trb = resp_post.json()
    assert trb["nome"] == payload["nome"]
    assert trb["cpfMascarado"] == "***.982.247-**"
    assert trb["terceirizadaId"] == TER_ALFA_1
    assert "id" in trb

    # Terceirizada 1 lista e enxerga seu trabalhador
    resp_get = client.get("/trabalhadores", headers=headers_terceirizada_1_alfa)
    assert resp_get.status_code == 200
    itens = resp_get.json()["itens"]
    assert any(t["id"] == trb["id"] for t in itens)


def test_h02_ca2_vincular_trabalhador_ao_contrato(
    client: TestClient,
    headers_admin_alfa: dict[str, str],
) -> None:
    """Valida alocação de trabalhador em contrato existente."""
    payload = {"trabalhadorId": TRB_ALFA_1}
    resp = client.post(
        f"/contratos/{CTR_ALFA_1}/alocacoes",
        json=payload,
        headers=headers_admin_alfa,
    )
    assert resp.status_code == 201
    aloc = resp.json()
    assert aloc["contratoId"] == CTR_ALFA_1
    assert aloc["trabalhadorId"] == TRB_ALFA_1
    assert aloc["semaforo"] in ("VERDE", "AMARELO", "VERMELHO")


def test_h02_ca3_upload_documento_pdf_valido(
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


def test_h02_ca4_upload_rejeita_arquivo_invalido_sem_assinatura_magica_retorna_415(
    client: TestClient,
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Arquivos que não são PDF ou JPEG são rejeitados com HTTP 415 Unsupported Media Type."""
    conteudo_falso = b"texto simples sem assinatura de PDF ou JPEG"
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
    assert resp.status_code == 415
    assert "application/problem+json" in resp.headers.get("content-type", "")
    assert resp.json().get("status") == 415


def test_h02_ca5_upload_excede_5mb_retorna_413(
    client: TestClient,
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Arquivo com mais de 5.000.000 bytes é rejeitado com HTTP 413 Payload Too Large."""
    conteudo_gigante = b"%PDF" + b"0" * 5_000_001
    arquivos = {"arquivo": ("laudo_pesado.pdf", io.BytesIO(conteudo_gigante), "application/pdf")}
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
    assert resp.status_code == 413
    assert "application/problem+json" in resp.headers.get("content-type", "")
    assert resp.json().get("status") == 413


def test_h02_ca6_cpf_digitos_invalidos_retorna_422(
    client: TestClient,
    headers_admin_alfa: dict[str, str],
) -> None:
    """CPF com dígitos verificadores matematicamente incorretos é rejeitado com HTTP 422."""
    payload = {
        "nome": "Trabalhador CPF Falso",
        "cpf": "123.456.789-01",  # Dígitos 01 são inválidos para essa raiz
        "terceirizadaId": TER_ALFA_1,
    }
    resp = client.post("/trabalhadores", json=payload, headers=headers_admin_alfa)
    assert resp.status_code == 422
    assert "application/problem+json" in resp.headers.get("content-type", "")


def test_h02_ca7_cpf_duplicado_retorna_409(
    client: TestClient,
    headers_admin_alfa: dict[str, str],
) -> None:
    """Tentativa de cadastrar CPF já existente no mesmo tenant retorna HTTP 409 Conflict."""
    payload = {
        "nome": "Duplicata do Carlos",
        "cpf": CPF_TRB_ALFA_1,
        "terceirizadaId": TER_ALFA_1,
    }
    resp = client.post("/trabalhadores", json=payload, headers=headers_admin_alfa)
    assert resp.status_code == 409
    assert "application/problem+json" in resp.headers.get("content-type", "")
    assert resp.json().get("status") == 409


def test_h02_ca8_alocacao_contrato_inexistente_retorna_404(
    client: TestClient,
    headers_admin_alfa: dict[str, str],
) -> None:
    """Alocação em contrato que não existe no tenant responde HTTP 404."""
    payload = {"trabalhadorId": TRB_ALFA_1}
    resp = client.post(
        "/contratos/ctr_inexistente_999/alocacoes",
        json=payload,
        headers=headers_admin_alfa,
    )
    assert resp.status_code == 404
    assert "application/problem+json" in resp.headers.get("content-type", "")


def test_h02_ca9_upload_tipo_documento_inexistente_retorna_404(
    client: TestClient,
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Envio de documento com tipoDocumentoId inexistente no tenant retorna HTTP 404."""
    pdf_conteudo = b"%PDF-1.4 documento valido"
    arquivos = {"arquivo": ("exame.pdf", io.BytesIO(pdf_conteudo), "application/pdf")}
    dados = {
        "tipoDocumentoId": "tip_inexistente_no_tenant",
        "validoAte": "2027-01-01",
    }
    resp = client.post(
        f"/trabalhadores/{TRB_ALFA_1}/documentos",
        files=arquivos,
        data=dados,
        headers=headers_terceirizada_1_alfa,
    )
    assert resp.status_code == 404
    assert "application/problem+json" in resp.headers.get("content-type", "")


def test_h03_ca1_analista_revisa_fila_e_gera_url_download(
    client: TestClient,
    headers_analista_alfa: dict[str, str],
) -> None:
    """Analista consulta documentos e obtém URL assinada para visualização."""
    resp_lista = client.get("/documentos", headers=headers_analista_alfa)
    assert resp_lista.status_code == 200
    assert "itens" in resp_lista.json()

    # Gera link de download para o documento existente no seed
    resp_url = client.post(
        f"/documentos/{DOC_ALFA_1_ASO}/url-download",
        headers=headers_analista_alfa,
    )
    assert resp_url.status_code == 200
    dados_url = resp_url.json()
    assert "url" in dados_url
    assert "expiraEm" in dados_url


def test_h03_ca2_analista_aprova_e_rejeita_documento(
    client: TestClient,
    headers_analista_alfa: dict[str, str],
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Cria documentos pendentes e valida aprovação e rejeição com motivo de 10+ caracteres."""
    # Cria documento 1 para aprovar
    pdf_bytes = b"%PDF-1.4 teste aprovacao"
    resp_doc1 = client.post(
        f"/trabalhadores/{TRB_ALFA_1}/documentos",
        files={"arquivo": ("doc1.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"tipoDocumentoId": "tip_aso", "validoAte": "2027-12-31"},
        headers=headers_terceirizada_1_alfa,
    )
    assert resp_doc1.status_code == 201
    doc1_id = resp_doc1.json()["id"]

    # Aprova documento 1
    resp_aprov = client.post(
        f"/documentos/{doc1_id}/aprovacao",
        headers=headers_analista_alfa,
    )
    assert resp_aprov.status_code == 200
    assert resp_aprov.json()["statusRevisao"] == "APROVADO"

    # Cria documento 2 para rejeitar
    resp_doc2 = client.post(
        f"/trabalhadores/{TRB_ALFA_1}/documentos",
        files={"arquivo": ("doc2.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"tipoDocumentoId": "tip_aso", "validoAte": "2027-12-31"},
        headers=headers_terceirizada_1_alfa,
    )
    assert resp_doc2.status_code == 201
    doc2_id = resp_doc2.json()["id"]

    # Rejeição com motivo detalhado (> 10 caracteres)
    motivo_payload = {"motivo": "CRM do médico emissor ilegível no carimbo da página 2."}
    resp_rej = client.post(
        f"/documentos/{doc2_id}/rejeicao",
        json=motivo_payload,
        headers=headers_analista_alfa,
    )
    assert resp_rej.status_code == 200
    doc_rej = resp_rej.json()
    assert doc_rej["statusRevisao"] == "REJEITADO"
    assert doc_rej["motivoRejeicao"] == motivo_payload["motivo"]


def test_h03_ca3_terceirizada_nao_pode_aprovar_documento_retorna_403(
    client: TestClient,
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Papel terceirizada é proibido de aprovar documentos (apenas admin e analista)."""
    resp = client.post(
        f"/documentos/{DOC_ALFA_1_ASO}/aprovacao",
        headers=headers_terceirizada_1_alfa,
    )
    assert resp.status_code == 403
    assert "application/problem+json" in resp.headers.get("content-type", "")


def test_h03_ca4_aprovacao_documento_nao_pendente_retorna_409(
    client: TestClient,
    headers_analista_alfa: dict[str, str],
) -> None:
    """Tentativa de aprovar documento que já está APROVADO retorna HTTP 409 Conflict."""
    resp = client.post(
        f"/documentos/{DOC_ALFA_1_ASO}/aprovacao",
        headers=headers_analista_alfa,
    )
    assert resp.status_code == 409
    assert "application/problem+json" in resp.headers.get("content-type", "")
    assert resp.json().get("status") == 409


def test_h03_ca5_rejeicao_motivo_menor_que_10_chars_retorna_422(
    client: TestClient,
    headers_analista_alfa: dict[str, str],
    headers_terceirizada_1_alfa: dict[str, str],
) -> None:
    """Justificativa de rejeição com menos de 10 caracteres é rejeitada com HTTP 422."""
    # Cria doc pendente
    resp_doc = client.post(
        f"/trabalhadores/{TRB_ALFA_1}/documentos",
        files={"arquivo": ("doc.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")},
        data={"tipoDocumentoId": "tip_aso", "validoAte": "2027-12-31"},
        headers=headers_terceirizada_1_alfa,
    )
    doc_id = resp_doc.json()["id"]

    resp = client.post(
        f"/documentos/{doc_id}/rejeicao",
        json={"motivo": "curto"},  # 5 caracteres < 10
        headers=headers_analista_alfa,
    )
    assert resp.status_code == 422
    assert "application/problem+json" in resp.headers.get("content-type", "")


def test_h03_ca6_isolamento_horizontal_trabalhador_e_documento_outro_tenant_retorna_404(
    client: TestClient,
    headers_admin_alfa: dict[str, str],
) -> None:
    """Admin de Alfa acessa trabalhador e documento de Beta -> 404 Problem Details."""
    resp_trb = client.get(f"/trabalhadores/{TRB_BETA_1}", headers=headers_admin_alfa)
    assert resp_trb.status_code == 404
    assert "application/problem+json" in resp_trb.headers.get("content-type", "")

    resp_doc = client.get(f"/documentos/{DOC_BETA_1_ASO}", headers=headers_admin_alfa)
    assert resp_doc.status_code == 404
    assert "application/problem+json" in resp_doc.headers.get("content-type", "")


def test_h03_ca7_isolamento_intra_tenant_terceirizada_distinta_retorna_404(
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
