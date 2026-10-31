"""Testes unitários da porta ArmazenamentoDocumentos e do adapter em memória.

Valida a convenção de isolamento multi-tenant, sanitização contra path traversal
e as operações básicas da porta sem depender de contêineres ou rede.
"""

import pytest

from habilita.armazenamento.memoria import MemoriaArmazenamento
from habilita.armazenamento.porta import (
    CaminhoInvalidoError,
    ObjetoNaoEncontradoError,
    validar_caminho,
)


def test_validar_caminho_sucesso_com_formato_padrao() -> None:
    caminho = validar_caminho("tnt_alfa", "doc_aso_123")
    assert caminho == "tenants/tnt_alfa/documentos/doc_aso_123"

    caminho_com_ext = validar_caminho("tnt-beta_99", "arquivo.pdf")
    assert caminho_com_ext == "tenants/tnt-beta_99/documentos/arquivo.pdf"


@pytest.mark.parametrize(
    ("tenant_id", "documento_id"),
    [
        ("../tnt_alfa", "doc_123"),
        ("tnt_alfa/..", "doc_123"),
        ("tnt/alfa", "doc_123"),
        ("tnt\\alfa", "doc_123"),
        ("tnt_alfa", "../doc_123"),
        ("tnt_alfa", "doc/123"),
        ("tnt_alfa", "doc\\123"),
        ("tnt_alfa", "../../etc/passwd"),
        ("..", "doc_123"),
        ("tnt_alfa", ".."),
        ("", "doc_123"),
        ("tnt_alfa", ""),
        ("   ", "doc_123"),
        ("tnt alfa", "doc_123"),
        ("tnt_alfa", "doc 123"),
        ("tnt@alfa", "doc_123"),
        ("tnt_alfa", "doc#123.pdf"),
        ("tnt_alfa", "doc?query=1"),
    ],
)
def test_validar_caminho_rejeita_tentativas_de_traversal_e_caracteres_invalidos(
    tenant_id: str, documento_id: str
) -> None:
    with pytest.raises(CaminhoInvalidoError):
        validar_caminho(tenant_id, documento_id)


def test_memoria_salvar_e_obter_url_leitura() -> None:
    storage = MemoriaArmazenamento(public_url="http://storage.local.test")
    conteudo = b"%PDF-1.4 conteudo de teste"

    caminho = storage.salvar(
        tenant_id="tnt_alfa",
        documento_id="doc_aso.pdf",
        conteudo=conteudo,
        content_type="application/pdf",
    )
    assert caminho == "tenants/tnt_alfa/documentos/doc_aso.pdf"

    url = storage.obter_url_leitura(
        tenant_id="tnt_alfa",
        documento_id="doc_aso.pdf",
        expira_em_segundos=600,
    )
    assert (
        url
        == "http://storage.local.test/mock-signed/tenants/tnt_alfa/documentos/doc_aso.pdf?exp=600"
    )

    guardado = storage.obter_conteudo("tnt_alfa", "doc_aso.pdf")
    assert guardado == (conteudo, "application/pdf")


def test_memoria_obter_url_documento_inexistente_lanca_erro() -> None:
    storage = MemoriaArmazenamento()
    with pytest.raises(ObjetoNaoEncontradoError):
        storage.obter_url_leitura("tnt_alfa", "doc_inexistente.pdf")


def test_memoria_excluir_remove_documento() -> None:
    storage = MemoriaArmazenamento()
    storage.salvar("tnt_alfa", "doc_excluir.pdf", b"dados", "application/pdf")

    # Exclusão bem-sucedida
    storage.excluir("tnt_alfa", "doc_excluir.pdf")

    # Não deve mais existir
    with pytest.raises(ObjetoNaoEncontradoError):
        storage.obter_url_leitura("tnt_alfa", "doc_excluir.pdf")

    # Exclusão repetida é idempotente
    storage.excluir("tnt_alfa", "doc_excluir.pdf")


def test_memoria_saude() -> None:
    storage = MemoriaArmazenamento()
    assert storage.saude() is True

    storage.definir_saude(False)
    assert storage.saude() is False


def test_memoria_garante_isolamento_estrito_entre_tenants() -> None:
    storage = MemoriaArmazenamento()
    storage.salvar("tnt_alfa", "doc_comum.pdf", b"dados do tenant alfa", "application/pdf")

    # O mesmo nome de documento em outro tenant não deve existir
    with pytest.raises(ObjetoNaoEncontradoError):
        storage.obter_url_leitura("tnt_beta", "doc_comum.pdf")
