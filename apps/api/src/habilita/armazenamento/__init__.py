"""Módulo de armazenamento de documentos do Habilita."""

from habilita.armazenamento.memoria import MemoriaArmazenamento
from habilita.armazenamento.porta import (
    ArmazenamentoDocumentos,
    ArmazenamentoError,
    CaminhoInvalidoError,
    ObjetoNaoEncontradoError,
    validar_caminho,
)
from habilita.armazenamento.supabase import SupabaseArmazenamento

__all__ = [
    "ArmazenamentoDocumentos",
    "ArmazenamentoError",
    "CaminhoInvalidoError",
    "MemoriaArmazenamento",
    "ObjetoNaoEncontradoError",
    "SupabaseArmazenamento",
    "validar_caminho",
]
