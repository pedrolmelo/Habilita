"""Teste de integração do adapter SupabaseArmazenamento contra o Storage local.

Marcado com @pytest.mark.integration para execução quando o Docker Compose estiver ativo.
"""

from __future__ import annotations

import urllib.request

import pytest

from habilita.armazenamento.porta import ObjetoNaoEncontradoError
from habilita.armazenamento.supabase import SupabaseArmazenamento
from habilita.config import get_settings


@pytest.mark.integration
def test_supabase_armazenamento_ciclo_de_vida_completo() -> None:
    settings = get_settings()
    tenant_id = "tnt_teste_integ"

    storage = SupabaseArmazenamento(
        tenant_id=tenant_id,
        base_url=settings.storage_url,
        service_key=settings.supabase_service_key.get_secret_value(),
        bucket=settings.storage_bucket,
        public_url=settings.storage_public_url,
    )

    # 1. Verificar saúde do serviço
    if not storage.saude():
        pytest.skip(
            "Supabase Storage local não disponível neste ambiente de teste "
            "(serviço storage ausente ou inativo no Compose)"
        )

    trabalhador_id = "trb_teste"
    documento_id = "doc_teste"
    conteudo_esperado = b"%PDF-1.4 conteudo binario de teste para integracao"

    caminho_salvo = ""
    try:
        # 2. Salvar documento
        caminho_salvo = storage.salvar(
            trabalhador_id=trabalhador_id,
            documento_id=documento_id,
            conteudo=conteudo_esperado,
            extensao="pdf",
        )
        prefixo_esperado = (
            f"tenants/{tenant_id}/trabalhadores/{trabalhador_id}/documentos/{documento_id}"
        )
        assert prefixo_esperado in caminho_salvo
        assert caminho_salvo.endswith(".pdf")

        # 3. Obter URL de leitura assinada (teto 300s)
        url_assinada = storage.obter_url_leitura(
            caminho=caminho_salvo,
            expira_em_segundos=300,
        )
        assert settings.storage_public_url in url_assinada
        assert "token=" in url_assinada

        # 4. Validar download via URL assinada (sem headers de autorização)
        url_busca = url_assinada.replace(settings.storage_public_url, settings.storage_url)
        with urllib.request.urlopen(url_busca, timeout=5) as resp:  # noqa: S310
            assert resp.status == 200
            conteudo_baixado = resp.read()
            assert conteudo_baixado == conteudo_esperado

        # 5. Documento inexistente deve lançar ObjetoNaoEncontradoError
        with pytest.raises(ObjetoNaoEncontradoError):
            storage.obter_url_leitura(
                trabalhador_id=trabalhador_id,
                documento_id=documento_id,
                nome_arquivo="inexistente_uuid.pdf",
            )

    finally:
        # 6. Excluir documento e garantir limpeza
        if caminho_salvo:
            storage.excluir(caminho=caminho_salvo)

    # 7. Após exclusão, obter URL assinada deve falhar com ObjetoNaoEncontradoError
    with pytest.raises(ObjetoNaoEncontradoError):
        storage.obter_url_leitura(caminho=caminho_salvo)
