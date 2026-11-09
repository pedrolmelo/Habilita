"""Módulo de armazenamento de documentos (Plano Custo Zero)."""

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
from habilita.armazenamento.supabase import SupabaseArmazenamento

__all__ = [
    "TETO_MAXIMO_EXPIRACAO_SEGUNDOS",
    "ArmazenamentoDocumentos",
    "ArmazenamentoError",
    "CaminhoInvalidoError",
    "ObjetoNaoEncontradoError",
    "SupabaseArmazenamento",
    "construir_caminho",
    "validar_e_resolver_caminho",
    "validar_id",
]
