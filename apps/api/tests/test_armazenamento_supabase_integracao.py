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

    storage = SupabaseArmazenamento(
        base_url=settings.storage_url,
        service_key=settings.supabase_service_key,
        bucket=settings.storage_bucket,
        public_url=settings.storage_public_url,
    )

    # 1. Verificar saúde do serviço
    if not storage.saude():
        pytest.skip(
            "Supabase Storage local não disponível neste ambiente de teste "
            "(serviço storage ausente ou inativo no Compose)"
        )

    tenant_id = "tnt_teste_integ"
    documento_id = "doc_teste_integracao.pdf"
    conteudo_esperado = b"%PDF-1.4 conteudo binario de teste para integracao"
    content_type = "application/pdf"

    try:
        # 2. Salvar documento
        caminho_salvo = storage.salvar(
            tenant_id=tenant_id,
            documento_id=documento_id,
            conteudo=conteudo_esperado,
            content_type=content_type,
        )
        assert caminho_salvo == f"tenants/{tenant_id}/documentos/{documento_id}"

        # 3. Obter URL de leitura assinada
        url_assinada = storage.obter_url_leitura(
            tenant_id=tenant_id,
            documento_id=documento_id,
            expira_em_segundos=300,
        )
        assert settings.storage_public_url in url_assinada
        assert "token=" in url_assinada

        # 4. Validar download via URL assinada (sem headers de autorização)
        # Para funcionar dentro do contêiner Docker (onde 127.0.0.1 é a própria API),
        # substituímos a URL pública pela base_url interna para a requisição de teste.
        url_busca = url_assinada.replace(settings.storage_public_url, settings.storage_url)
        with urllib.request.urlopen(url_busca, timeout=5) as resp:  # noqa: S310
            assert resp.status == 200
            conteudo_baixado = resp.read()
            assert conteudo_baixado == conteudo_esperado

        # 5. Documento inexistente deve lançar ObjetoNaoEncontradoError
        with pytest.raises(ObjetoNaoEncontradoError):
            storage.obter_url_leitura(tenant_id=tenant_id, documento_id="nao_existe.pdf")

    finally:
        # 6. Excluir documento e garantir limpeza
        storage.excluir(tenant_id=tenant_id, documento_id=documento_id)

    # 7. Após exclusão, obter URL assinada deve falhar com ObjetoNaoEncontradoError
    with pytest.raises(ObjetoNaoEncontradoError):
        storage.obter_url_leitura(tenant_id=tenant_id, documento_id=documento_id)
