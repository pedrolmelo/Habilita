"""Testes unitários da porta ArmazenamentoDocumentos e do adapter em memória.

Valida a convenção de isolamento multi-tenant, hierarquia da ADR 0006 v3,
sanitização contra path traversal, limite de 300s na URL assinada e
as operações básicas da porta sem depender de contêineres ou rede.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from habilita.armazenamento.porta import (
    CaminhoInvalidoError,
    ObjetoNaoEncontradoError,
    construir_caminho,
    validar_e_resolver_caminho,
    validar_id,
)
from habilita.config import CHAVE_DEMO_SUPABASE, Settings

from .memoria_armazenamento import MemoriaArmazenamento


# -----------------------------------------------------------------------------
# Validação de IDs e Caminho Canônico (ADR 0006 v3)
# -----------------------------------------------------------------------------
def test_validar_id_sucesso() -> None:
    assert validar_id("tnt_alfa", "tenant_id") == "tnt_alfa"
    assert validar_id("trb-123_45", "trabalhador_id") == "trb-123_45"
    assert validar_id("doc_aso_2026", "documento_id") == "doc_aso_2026"


@pytest.mark.parametrize(
    "id_invalido",
    [
        "",
        "   ",
        "tnt/alfa",
        "tnt\\alfa",
        "../tnt",
        "tnt/..",
        "tnt@alfa",
        "tnt#123",
        "tnt?query=1",
        "tnt\nalfa",  # re.fullmatch previne quebras de linha
        "a" * 65,  # limite de 64 caracteres
    ],
)
def test_validar_id_rejeita_caracteres_invalidos_e_traversal(id_invalido: str) -> None:
    with pytest.raises(CaminhoInvalidoError):
        validar_id(id_invalido, "id_teste")


def test_construir_caminho_formato_adr_0006() -> None:
    caminho = construir_caminho(
        tenant_id="tnt_alfa",
        trabalhador_id="trb_123",
        documento_id="doc_aso",
        nome_arquivo="uuid_exemplo.pdf",
    )
    assert caminho == "tenants/tnt_alfa/trabalhadores/trb_123/documentos/doc_aso/uuid_exemplo.pdf"

    caminho_mini = construir_caminho(
        tenant_id="tnt_alfa",
        trabalhador_id="trb_123",
        documento_id="doc_aso",
        nome_arquivo="uuid_exemplo_mini.jpg",
    )
    esperado = "tenants/tnt_alfa/trabalhadores/trb_123/documentos/doc_aso/uuid_exemplo_mini.jpg"
    assert caminho_mini == esperado


def test_validar_e_resolver_caminho_valida_isolamento_por_tenant() -> None:
    caminho_valido = "tenants/tnt_alfa/trabalhadores/trb_1/documentos/doc_1/uuid1.pdf"
    assert validar_e_resolver_caminho("tnt_alfa", caminho=caminho_valido) == caminho_valido

    # Rejeita caminho pertencente a outro tenant (violação horizontal)
    caminho_outro_tenant = "tenants/tnt_beta/trabalhadores/trb_1/documentos/doc_1/uuid1.pdf"
    with pytest.raises(CaminhoInvalidoError, match="Violação de isolamento multi-tenant"):
        validar_e_resolver_caminho("tnt_alfa", caminho=caminho_outro_tenant)


# -----------------------------------------------------------------------------
# Operações no Adapter em Memória
# -----------------------------------------------------------------------------
def test_memoria_salvar_gera_caminho_padrao_e_miniatura() -> None:
    storage = MemoriaArmazenamento(tenant_id="tnt_alfa", public_url="http://storage.local.test")
    conteudo = b"%PDF-1.4 conteudo de teste"

    caminho = storage.salvar(
        trabalhador_id="trb_1",
        documento_id="doc_aso",
        conteudo=conteudo,
        extensao="pdf",
        arquivo_uuid="fixo-123",
    )
    assert caminho == "tenants/tnt_alfa/trabalhadores/trb_1/documentos/doc_aso/fixo-123.pdf"

    # Salva miniatura
    caminho_mini = storage.salvar(
        trabalhador_id="trb_1",
        documento_id="doc_aso",
        conteudo=b"\xff\xd8\xff dados jpeg",
        extensao="jpg",
        miniatura=True,
        arquivo_uuid="fixo-123",
    )
    esperado_mini = "tenants/tnt_alfa/trabalhadores/trb_1/documentos/doc_aso/fixo-123_mini.jpg"
    assert caminho_mini == esperado_mini


def test_h12_ca3_url_assinada_teto_maximo_300s() -> None:
    """H12.CA3: URL assinada deve ter validade máxima de 300 segundos."""
    storage = MemoriaArmazenamento(tenant_id="tnt_alfa")
    caminho = storage.salvar(
        trabalhador_id="trb_1",
        documento_id="doc_1",
        conteudo=b"%PDF-1.4 dados",
        extensao="pdf",
    )

    # 300s é aceito
    url_300 = storage.obter_url_leitura(caminho=caminho, expira_em_segundos=300)
    assert "exp=300" in url_300

    # 301s estoura o teto e lança ValueError
    with pytest.raises(ValueError, match="Tempo de expiração deve ser entre 1 e 300 segundos"):
        storage.obter_url_leitura(caminho=caminho, expira_em_segundos=301)

    # 0s ou negativo é inválido
    with pytest.raises(ValueError, match="Tempo de expiração deve ser entre 1 e 300 segundos"):
        storage.obter_url_leitura(caminho=caminho, expira_em_segundos=0)


def test_memoria_obter_url_documento_inexistente_lanca_erro() -> None:
    storage = MemoriaArmazenamento(tenant_id="tnt_alfa")
    with pytest.raises(ObjetoNaoEncontradoError):
        storage.obter_url_leitura(
            trabalhador_id="trb_1",
            documento_id="doc_inexistente",
            nome_arquivo="uuid.pdf",
        )


def test_memoria_excluir_e_idempotente() -> None:
    storage = MemoriaArmazenamento(tenant_id="tnt_alfa")
    caminho = storage.salvar(
        trabalhador_id="trb_1",
        documento_id="doc_excluir",
        conteudo=b"dados",
        extensao="pdf",
    )

    # Exclusão inicial
    storage.excluir(caminho=caminho)

    # Não deve mais existir para leitura
    with pytest.raises(ObjetoNaoEncontradoError):
        storage.obter_url_leitura(caminho=caminho)

    # Segunda exclusão do mesmo caminho é idempotente (não lança exceção)
    storage.excluir(caminho=caminho)


def test_memoria_saude() -> None:
    storage = MemoriaArmazenamento(tenant_id="tnt_alfa")
    assert storage.saude() is True

    storage.definir_saude(False)
    assert storage.saude() is False


# -----------------------------------------------------------------------------
# Validações de Configuração e Segredos (Settings)
# -----------------------------------------------------------------------------
def test_settings_em_prod_rejeita_chave_vazia_ou_demo() -> None:
    """Em ambiente produtivo, a API deve falhar se não houver chave real fornecida."""
    with pytest.raises(ValidationError):
        Settings(app_env="prod", supabase_service_key=SecretStr(""))

    with pytest.raises(ValidationError):
        Settings(app_env="prod", supabase_service_key=SecretStr(CHAVE_DEMO_SUPABASE))

    # Chave customizada em prod é aceita
    cfg = Settings(app_env="prod", supabase_service_key=SecretStr("super-secret-key-prod-12345"))
    assert cfg.supabase_service_key.get_secret_value() == "super-secret-key-prod-12345"
